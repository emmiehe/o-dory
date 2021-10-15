# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

# import odoo.addons.decimal_precision as dp
import json

# class BitMaps:
#     def __init__(self, width):
#         self.width = width
#         # the index of the word is determined by the user's salt
#         self.bitmaps = dict()  # doc_id: [0, 0, 1, 1...]


class ServerDatabase(models.Model):
    _name = "server.database"
    _description = "server database"

    name = fields.Char("Name")
    bitmap_width = fields.Integer("Bitmaps Width", default=1000, readonly=1)
    bitmaps = fields.Binary("Bitmaps", attachment=False)
    bitmaps_str = fields.Char(
        "Bitmaps String", compute="_compute_bitmaps_str", store=True
    )  # this field should be removed later

    def _retrieve_column(self, encrypted_keyword, salt=None):
        for sdb in self:
            bitmaps = json.loads(sdb.bitmaps)
            index = encrypted_keyword % sdb.bitmap_width
            print("===== retrieve index is ", index)
            return json.dumps([[k, v[index]] for [k, v] in bitmaps.items()])

    @api.depends("bitmaps")
    def _compute_bitmaps_str(self):
        for sdb in self:
            dic = json.loads(sdb.bitmaps)
            string = ""
            for k, v in dic.items():
                string += "{}: {}\n".format(k, v)
            sdb.bitmaps_str = string

    @api.model_create_multi
    def create(self, vals_list):
        res_ids = super(ServerDatabase, self).create(vals_list)
        # when a server database is created, there should be a bitmap table setup
        for res_id in res_ids:
            res_id.bitmaps = json.dumps(dict())
        return res_ids


class EncryptedDocument(models.Model):
    _name = "encrypted.document"
    _description = "encrypted document"

    name = fields.Char("Name")
    blob = fields.Text("Encrypted Blob")  # maybe this should be binary
    database_id = fields.Many2one(
        "server.database", ondelete="restrict", string="Database"
    )
