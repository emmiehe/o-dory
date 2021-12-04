from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import ujson as json
import logging, random
import numpy as np
import sycret

_logger = logging.getLogger(__name__)

eq = sycret.EqFactory(n_threads=10)


class ResUsers(models.Model):
    _inherit = "res.users"

    def get_folder(self):
        self.ensure_one()
        folder_ids = self.env["server.folder"].search(
            [("user_id", "=", self.id)], limit=1
        )  # one user should only have one folder on a server
        if not folder_ids:
            raise ValidationError(_("Cannot find related folder."))
        folder_id = folder_ids[0]
        version = folder_id.bitmap_version
        bitmaps = folder_id.bitmaps
        return folder_id, bitmaps, version

    def get_bitmaps_doc_versions_by_doc_ids(self, doc_ids):
        self.ensure_one()
        folder_id, bitmaps, version = self.get_folder()
        docs = self.env["encrypted.document"].search_read(
            [
                ("user_id", "=", self.id),
                ("folder_id", "=", folder_id.id),
                ("id", "in", doc_ids),
            ],
            fields=["version"],
        )
        doc_versions = {doc.get("id"): doc.get("version") for doc in docs}
        bitmaps = folder_id.bitmaps_get(folder_id.bitmaps_deserialize(bitmaps), doc_ids)
        ret = [
            [bitmaps[i], doc_versions.get(doc_ids[i])] for i in range(len(doc_versions))
        ]
        return json.dumps(ret)

    def get_bitmaps_version(self):
        __, __, version = self.get_folder()
        return version

    def get_indexed_document_count(self):
        folder_id, bitmaps, __ = self.get_folder()
        return len(folder_id.bitmaps_deserialize(bitmaps))

    def upload_encrypted_files(self, encrypted_data):
        self.ensure_one()
        encrypted_documents, bloom_filter_rows, new_col_macs = encrypted_data
        folder_id, bitmaps, version = self.get_folder()

        # upload the encrypted_document
        doc_ids = self.env["encrypted.document"].create(
            [
                {
                    "blob": encrypted_document,
                    "folder_id": folder_id.id,
                    "user_id": self.id,
                    "version": doc_version,
                }
                for (encrypted_document, doc_version) in encrypted_documents
            ]
        )

        if not doc_ids:
            # todo: need some better handling
            raise ValidationError(_("Error creating files."))

        # bitmap operations
        bitmaps_obj = folder_id.bitmaps_deserialize(bitmaps)

        bitmaps_obj = folder_id.bitmaps_update(
            bitmaps_obj, doc_ids.ids, bloom_filter_rows
        )
        new_bitmaps = folder_id.bitmaps_serialize(bitmaps_obj)

        folder_id.sudo().write(
            {
                "bitmaps": new_bitmaps,
                "bitmap_version": version + 1,
                "col_macs": new_col_macs,
            }
        )

        return doc_ids.ids

    def remove_encrypted_files_by_ids(self, data):
        self.ensure_one()
        folder_id, bitmaps, version = self.get_folder()
        fids, new_col_macs = data

        # iterate over doc_ids to avoid deleting files not belonging to the user
        doc_ids = self.env["encrypted.document"].search(
            [("id", "in", fids), ("user_id", "=", self.id)]
        )

        res = True
        if doc_ids:
            if set(doc_ids.ids) != set(fids):
                _logger.warning(
                    "User {} attempts to delete non-existent files {}".format(
                        self.id, fids
                    )
                )
                return False

            ddoc_ids = [str(i) for i in doc_ids.ids]
            doc_ids.unlink()
            # deserialize
            bitmaps_obj = folder_id.bitmaps_deserialize(bitmaps)
            res = folder_id.bitmaps_remove(bitmaps_obj, ddoc_ids)
            new_bitmaps = folder_id.bitmaps_serialize(bitmaps_obj)

            folder_id.sudo().write(
                {
                    "bitmaps": new_bitmaps,
                    "bitmap_version": version + 1,
                    "col_macs": new_col_macs,
                }
            )

        return res

    def update_files_by_ids(self, encrypted_data):
        fids, encrypted_documents, bloom_filter_rows, new_col_macs = encrypted_data
        folder_id, bitmaps, version = self.get_folder()

        # verify the old file exists
        doc_ids = self.env["encrypted.document"].search(
            [("user_id", "=", self.id), ("id", "in", fids)]
        )
        if not doc_ids:
            raise ValidationError(_("Error creating file."))

        if len(fids) != len(doc_ids):
            return False

        for i in range(len(doc_ids)):

            doc_id = doc_ids[i]
            encrypted_document, doc_version = encrypted_documents[i]

            doc_id.write({"blob": encrypted_document, "version": doc_version})

        # bitmap operations
        bitmaps_obj = folder_id.bitmaps_deserialize(bitmaps)
        bitmaps_obj = folder_id.bitmaps_update(
            bitmaps_obj, doc_ids.ids, bloom_filter_rows
        )
        new_bitmaps = folder_id.bitmaps_serialize(bitmaps_obj)

        folder_id.sudo().write(
            {
                "bitmaps": new_bitmaps,
                "bitmap_version": version + 1,
                "col_macs": new_col_macs,
            }
        )

        return True

    # well this is not really necessary
    def retrieve_doc_ids(self):
        self.ensure_one()

        docs = self.env["encrypted.document"].search_read(
            [("user_id", "=", self.id)], fields=["id"]
        )

        ids = [doc.get("id") for doc in docs]

        return ids

    def retrieve_doc_versions(self):
        self.ensure_one()

        docs = self.env["encrypted.document"].search_read(
            [("user_id", "=", self.id)], fields=["version"]
        )
        return docs

    def retrieve_col_macs(self):
        self.ensure_one()

        folders = self.env["server.folder"].search_read(
            [("user_id", "=", self.id)], fields=["col_macs"]
        )

        col_macs = [folder.get("col_macs") for folder in folders]

        return col_macs[0]  # this is already serialized

    def retrieve_encrypted_files_by_ids(self, fids):
        self.ensure_one()

        # iterate over doc_ids to avoid deleting files not belonging to the user
        doc_ids = self.env["encrypted.document"].search(
            [("id", "in", fids), ("user_id", "=", self.id)]
        )

        if len(doc_ids) < len(fids):
            _logger.warning(
                "User {} attempts to retrieve non-existent files {}".format(
                    self.id, fids
                )
            )

        return [d.blob for d in doc_ids]

    # this is the naive model
    # all_indices = [[1, 2, 5], [9, 39, 4], [4, 7, 8]]
    # should return [[doc id1, doc id2, ...], [], []]
    def search_documents_by_keyword_indices(self, all_indices):
        self.ensure_one()
        # todo: the returned bitmaps should be deserialized?
        folder_id, bitmaps, version = self.get_folder()
        cols, row_to_doc = folder_id.bitmaps_flip(
            folder_id.bitmaps_deserialize(bitmaps)
        )
        all_ret = [[] for i in all_indices]
        if not cols:
            return all_ret
        # i is row
        for i in range(len(cols[0])):
            # j is return slot
            for j, indices in enumerate(all_indices):
                # k is the actual index
                if all([cols[k][i] for k in indices]):
                    all_ret[j].append(row_to_doc.get(i))

        return all_ret

    # server evals the secret
    def server_search(self, y, secrets):
        _logger.warning("Started server search")
        secrets = json.loads(secrets)
        folder_id, bitmaps, version = self.get_folder()
        doc_versions = self.retrieve_doc_versions()
        bitmaps = folder_id.bitmaps_deserialize(bitmaps)
        cols, row_to_doc = folder_id.bitmaps_flip(bitmaps)
        doc_count = len(bitmaps)
        bloom_filter_k = folder_id.bitmap_width
        results = [[0 for x in range(doc_count)] for y in range(bloom_filter_k)]
        for j, s in enumerate(secrets):
            x, k = s
            x = np.array(x, dtype=np.int32)
            k = np.array(k, dtype=np.uint8)
            output = eq.eval(y, x, k)
            output = output.tolist()
            for i in range(doc_count):
                results[j][i] ^= output[i] & cols[j][i]
        _logger.warning("Done server search")

        # return results, list(row_to_doc.items()), doc_versions
        return json.dumps((results, list(row_to_doc.items()), doc_versions))
