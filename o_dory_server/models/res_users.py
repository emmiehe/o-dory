from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import json, random
import logging

_logger = logging.getLogger(__name__)


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

    def get_bitmaps_version(self):
        __, __, version = self.get_folder()
        return version

    def upload_encrypted_files(self, encrypted_data):
        self.ensure_one()
        encrypted_documents, bloom_filter_rows = encrypted_data
        folder_id, bitmaps, version = self.get_folder()

        # upload the encrypted_document
        doc_ids = self.env["encrypted.document"].create(
            [
                {
                    "blob": encrypted_document,
                    "folder_id": folder_id.id,
                    "user_id": self.id,
                }
                for encrypted_document in encrypted_documents
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

        folder_id.sudo().write({"bitmaps": new_bitmaps, "bitmap_version": version + 1})

        return doc_ids.ids

    def remove_encrypted_files_by_ids(self, fids):
        self.ensure_one()
        folder_id, bitmaps, version = self.get_folder()

        # iterate over doc_ids to avoid deleting files not belonging to the user
        doc_ids = self.env["encrypted.document"].search(
            [("id", "in", fids), ("user_id", "=", self.id)]
        )

        if len(doc_ids) < len(fids):
            _logger.warning(
                "User {} attempts to delete non-existent files {}".format(self.id, fids)
            )

        if doc_ids:
            ddoc_ids = [str(i) for i in doc_ids.ids]
            doc_ids.unlink()
            # deserialize
            bitmaps_obj = folder_id.bitmaps_deserialize(bitmaps)

            res = folder_id.bitmaps_remove(bitmaps_obj, ddoc_ids)

            new_bitmaps = folder_id.bitmaps_serialize(bitmaps_obj)

            folder_id.sudo().write(
                {"bitmaps": new_bitmaps, "bitmap_version": version + 1}
            )

        return True

    def update_files_by_ids(self, encrypted_data):
        fids, encrypted_documents, bloom_filter_rows = encrypted_data
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
            encrypted_document = encrypted_documents[i]

            doc_id.write({"blob": encrypted_document})

        # bitmap operations
        bitmaps_obj = folder_id.bitmaps_deserialize(bitmaps)
        bitmaps_obj = folder_id.bitmaps_update(
            bitmaps_obj, doc_ids.ids, bloom_filter_rows
        )
        new_bitmaps = folder_id.bitmaps_serialize(bitmaps_obj)

        folder_id.sudo().write({"bitmaps": new_bitmaps, "bitmap_version": version + 1})

        return True

    # well this is not really necessary
    def retrieve_doc_ids(self):
        self.ensure_one()

        docs = self.env["encrypted.document"].search_read(
            [("user_id", "=", self.id)], fields=["id"]
        )

        ids = [doc.get("id") for doc in docs]

        return ids

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
