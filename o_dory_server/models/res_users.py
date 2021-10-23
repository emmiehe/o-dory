from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import json, random
import logging

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = "res.users"

    # get partitions and verify version numbers
    def get_verified_partitions(self):
        self.ensure_one()
        partition_ids = self.env["server.folder.partition"].search(
            [("user_id", "=", self.id)], order="bitmap_version desc"
        )
        if not partition_ids:
            raise ValidationError(_("Cannot find related partitions."))
        # make sure the versions of the partitions are the same
        version = partition_ids[0].bitmap_version
        bitmaps = partition_ids[0].bitmaps

        for i in range(1, len(partition_ids)):
            partition_id = partition_ids[i]
            if partition_id.bitmap_version != version:
                # force write
                # todo: multi write?
                partition_id.sudo().write(
                    {"bitmaps": bitmaps, "bitmap_version": version}
                )

        return version, bitmaps, partition_ids

    def upload_encrypted_file(self, encrypted_document, bloom_filter_row):
        for user_id in self:
            version, bitmaps, partition_ids = user_id.get_verified_partitions()

            # upload the encrypted_document
            doc_id = user_id.env["encrypted.document"].create(
                {
                    "blob": encrypted_document,
                    "partition_id": random.choice(partition_ids).id,
                    "user_id": user_id.id,
                }
            )

            if not doc_id:
                raise ValidationError(_("Error creating file."))

            # deserialize
            search_index_map = json.loads(bitmaps)
            search_index_map[doc_id.id] = bloom_filter_row

            new_bitmaps = json.dumps(search_index_map)

            partition_ids.sudo().write(
                {"bitmaps": new_bitmaps, "bitmap_version": version + 1}
            )

        return True

    def remove_encrypted_file_by_ids(self, fids):
        self.ensure_one()
        version, bitmaps, partition_ids = self.get_verified_partitions()

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
            search_index_map = json.loads(bitmaps)
            for doc_id in ddoc_ids:
                if doc_id in search_index_map.keys():
                    _logger.warning(
                        "User {} deleted file {} \n {}".format(
                            self.id, doc_id, search_index_map
                        )
                    )
                    del search_index_map[doc_id]

            new_bitmaps = json.dumps(search_index_map)

            partition_ids.sudo().write(
                {"bitmaps": new_bitmaps, "bitmap_version": version + 1}
            )

        return True
