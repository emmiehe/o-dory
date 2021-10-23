# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

# import odoo.addons.decimal_precision as dp
import json

# this class represents a physical server database/filesystem
class ServerDatabase(models.Model):
    _name = "server.database"
    _description = "Database"

    name = fields.Char("Name")
    # admin has access to a server database, for future demo usage
    user_id = fields.Many2one("res.users", string="Database Admin")
    available = fields.Boolean(
        "Available",
        help="This field indicates whether a server is available for the customers (user file storage). It would not be available if this server is used for other purposes (a dedicated server), or it is a master.",
    )


# each user has a folder on the server
class ServerFolder(models.Model):
    _name = "server.folder"
    _description = "Folder"

    name = fields.Char("Name")
    user_id = fields.Many2one(
        "res.users", ondelete="cascade", string="User", required=1
    )
    partition_ids = fields.One2many(
        "server.folder.partition", "folder_id", string="Partitions", readonly=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        # when a folder is created, the partitions need to be allocated to all servers
        # for now I assume server size is fixed
        # TODO: we might need to think about expanding partitions to newly spawned servers?
        db_ids = self.env["server.database"].search([("available", "=", True)])
        if len(db_ids) < 2:
            raise ValidationError(
                _("Cannot create a user folder: less than two servers available.")
            )

        res_ids = super(ServerFolder, self).create(vals_list)

        partition_data = []
        for res_id in res_ids:
            for db_id in db_ids:
                partition_data.append(
                    {
                        "name": "{}({})".format(res_id.name, db_id.name),
                        "folder_id": res_id.id,
                        "database_id": db_id.id,
                    }
                )

        # batch create partitions, note that bitmaps are created in partition create
        self.env["server.folder.partition"].create(partition_data)
        return res_ids


# a folder will have multiple partitions,
# each partition resides in a different database
class ServerFolderPartition(models.Model):
    _name = "server.folder.partition"
    _description = "Folder Partition"

    name = fields.Char("Name")
    folder_id = fields.Many2one(
        "server.folder", ondelete="cascade", string="Folder", required=1
    )
    database_id = fields.Many2one(
        "server.database", ondelete="restrict", string="Database", required=1
    )
    user_id = fields.Many2one(related="folder_id.user_id")

    bitmap_version = fields.Integer("Bitmap Version")
    bitmap_width = fields.Integer("Bitmap Width", default=7)
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
        items = bitmaps_obj.items()
        cols = [[0] * len(items)] * self.bitmap_width
        row_to_doc = dict()
        for i in range(len(items)):
            doc_id, row = items[i]
            row_to_doc[i] = doc_id
            for j in range(len(row)):
                cols[j][i] = row[j]
        return cols, row_to_doc

    def bitmaps_update(self, bitmaps_obj, doc_id, row):
        doc_id = str(doc_id)
        bitmaps_obj[doc_id] = row
        return bitmaps_obj

    def bitmaps_remove(self, bitmaps_obj, doc_id):
        doc_id = str(doc_id)
        if doc_id in bitmaps_obj.keys():
            del bitmaps_obj[doc_id]
            return True
        return False

    @api.depends("bitmaps")
    def _compute_bitmaps_str(self):
        for pid in self:
            dic = pid.bitmaps_deserialize(pid.bitmaps)
            string = ""
            for k, v in dic.items():
                string += "{}: {}\n".format(k, v)
            pid.bitmaps_str = string

    @api.model_create_multi
    def create(self, vals_list):
        res_ids = super(ServerFolderPartition, self).create(vals_list)
        # when a server database is created, there should be a bitmap table setup
        for res_id in res_ids:
            res_id.bitmaps = res_id.bitmaps_serialize(res_id.bitmaps_create())
        return res_ids


class EncryptedDocument(models.Model):
    _name = "encrypted.document"
    _description = "encrypted document"

    # not sure if we really need a name for the file, but keep it for now
    # name = fields.Char("Name")
    blob = fields.Text("Encrypted Blob")  # maybe this should be binary
    partition_id = fields.Many2one(
        "server.folder.partition", ondelete="restrict", string="Partition"
    )
    user_id = fields.Many2one(related="partition_id.user_id")
