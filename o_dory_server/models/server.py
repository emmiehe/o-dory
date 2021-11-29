# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

# import odoo.addons.decimal_precision as dp
import ujson as json


# each user has a folder on the server
class ServerFolder(models.Model):
    _name = "server.folder"
    _description = "Folder"

    name = fields.Char("Name")
    user_id = fields.Many2one(
        "res.users", ondelete="cascade", string="User", required=1
    )

    bitmap_version = fields.Integer("Bitmap Version")
    bitmap_width = fields.Integer("Bitmap Width", default=128)
    bitmaps = fields.Binary("Bitmaps", attachment=False)
    # a field for display only
    bitmaps_str = fields.Char(
        "Bitmaps String", compute="_compute_bitmaps_str", store=True
    )  # this field should be removed later

    # we need some bitmaps operations
    # for now the bitmaps is a dictionary,
    # key is the str(id) of the encrypted document
    # value is a list of 0s and 1s, each index indicates a keyword
    def bitmaps_create(self):
        return dict()

    def bitmaps_serialize(self, bitmaps_obj):
        return json.dumps(bitmaps_obj)

    def bitmaps_deserialize(self, bitmaps_serialized):
        return json.loads(bitmaps_serialized)

    # usually our bitmaps looks like this
    # doc_id: [0, 1, 0, ...]
    # doc_id: [0, 1, 1, ...]
    # doc_id: [1, 1, 0, ...]
    # now we want to get each column,
    # should give a 2d array and a map of row_index to doc_id
    def bitmaps_flip(self, bitmaps_obj):
        self.ensure_one()
        items = list(bitmaps_obj.items())
        cols = []
        for i in range(self.bitmap_width):
            cols.append([0] * len(items))
        row_to_doc = dict()
        for i in range(len(items)):
            doc_id, row = items[i]
            row_to_doc[i] = doc_id
            for j in range(len(row)):
                cols[j][i] = row[j]
        # print("...", cols, row_to_doc)
        return cols, row_to_doc

    def bitmaps_update(self, bitmaps_obj, doc_ids, rows):
        for i in range(len(doc_ids)):
            doc_id = str(doc_ids[i])
            bitmaps_obj[doc_id] = rows[i]
        return bitmaps_obj

    def bitmaps_remove(self, bitmaps_obj, doc_ids):
        count, removed = len(doc_ids), 0
        for doc_id in doc_ids:
            doc_id = str(doc_id)
            if doc_id in bitmaps_obj.keys():
                del bitmaps_obj[doc_id]
                removed += 1
        return count == removed

    @api.depends("bitmaps")
    def _compute_bitmaps_str(self):
        for fid in self:
            dic = fid.bitmaps_deserialize(fid.bitmaps) if fid.bitmaps else {}
            fid.bitmaps_str = "\n".join(
                ["{}: {}".format(k, v) for (k, v) in dic.items()]
            )

    @api.model_create_multi
    def create(self, vals_list):
        res_ids = super(ServerFolder, self).create(vals_list)
        # when a server folder is created, there should be a bitmap table setup
        for res_id in res_ids:
            res_id.bitmaps = res_id.bitmaps_serialize(res_id.bitmaps_create())
        return res_ids


class EncryptedDocument(models.Model):
    _name = "encrypted.document"
    _description = "encrypted document"

    # not sure if we really need a name for the file, but keep it for now
    # name = fields.Char("Name")
    blob = fields.Binary("Encrypted Blob")  # maybe this should be binary
    folder_id = fields.Many2one("server.folder", ondelete="restrict", string="Folder")
    user_id = fields.Many2one(related="folder_id.user_id")
    version = fields.Char("Version")
