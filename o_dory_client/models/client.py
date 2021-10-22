# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

# import odoo.addons.decimal_precision as dp
import json

 
class ODoryAccount(models.Model):
    _name = "o.dory.account"
    _description = "O-DORY Account"

    name = fields.Char("Name")

    # we need to store user's account information on the o-dory client
    # active = fields.Boolean(string='Active', default=True)
    oid = fields.Integer(string="O-DORY ID", required=True)
    username = fields.Char(string="O-DORY Username", required=True)
    password = fields.Char(string="O-DORY Password", required=True)


    # misc for client

    # make sure servers are all available
    def verify_connection(self):  # this should actually be a signing in
        return True
    
    # verify if server partitions all have the same version
    def verify_server_partitions(self):
        return True
    
    # ideally we also let the account object handle uploading, removing,
    # and updating (removing and uploading)

    # given a raw file, we should upload to a partition
    # (randomly for now as it is out of the scope)
    # we also should add a row to every partition's bitmaps
    # (or we can tell the master and let the master to do it)
    def upload(self, raw_file):
        return True

    # given a document id, we should remove the file from the server
    # the corresponding bitmaps row also need to be removed
    def remove(self, fid):
        return True


    # updating old file with the new raw file
    def update(self, fid, new_raw_file):
        self.remove(fid)
        self.upload(new_raw_file)
