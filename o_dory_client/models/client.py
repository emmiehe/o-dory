# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from xmlrpc import client

# import odoo.addons.decimal_precision as dp
import json, random

SAMPLE_KEYWORDS = ["apple", "berry", "carrot", "date"]


class ODoryAccount(models.Model):
    _name = "o.dory.account"
    _description = "O-DORY Account"

    name = fields.Char("Name", required=True)

    # we need to store user's account information on the o-dory client
    # active = fields.Boolean(string='Active', default=True)
    oid = fields.Integer(string="O-DORY ID", required=True)
    account = fields.Char(string="O-DORY Account", required=True)
    password = fields.Char(string="O-DORY Password", required=True)
    url = fields.Char(string="O-DORY Server URL", required=True)
    db = fields.Char(
        string="Odoo Server DB",
        required=True,
        help="This is Odoo specific term. Do not confuse this with O-DORY database",
    )
    bloom_filter_k = fields.Integer("Bitmap Width", default=7)

    # misc for client
    def connect(self):
        self.ensure_one()
        # Logging in
        common = client.ServerProxy("{}/xmlrpc/2/common".format(self.url))
        # print(common.version())
        uid = common.authenticate(self.db, self.account, self.password, {})
        # getting models
        models = client.ServerProxy("{}/xmlrpc/2/object".format(self.url))
        return uid, models

    # make sure servers are all available
    def verify_connection(self):
        uid, models = self.connect()
        if uid and models:
            raise UserError(_("Connection Test Succeeded!"))
        else:
            raise ValidationError(_("Connection Test Failed. {} ".format(models)))

    # verify if server partitions all have the same version
    def verify_server_partitions(self):
        return True

    # for now this is a fake function
    def extract_keywords(self, raw_file):
        return random.choices(SAMPLE_KEYWORDS, k=2)

    # todo: implement this seriously
    def compute_word_index(self, word):
        self.ensure_one()
        return hash(word) % self.bloom_filter_k

    def make_bloom_filter_row(self, keywords):
        self.ensure_one()
        res = [0] * self.bloom_filter_k
        for keyword in keywords:
            i = self.compute_word_index(keyword)
            res[i] = 1
        return res

    # we don't really care about actual files for now
    def encrypt(self, raw):
        return raw

    # let the account object handle uploading, removing,
    # and updating (removing and uploading)

    # given a raw file, we should upload to a partition
    # (randomly for now as it is out of the scope)
    # we also should add a row to every partition's bitmaps
    # (or we can tell the master and let the master to do it)
    def upload(self, raw_file):
        uid, models = self.connect()
        if not uid:
            raise ValidationError(_("Connection Failed."))

        keywords = self.extract_keywords(raw_file)
        row = self.make_bloom_filter_row(keywords)
        encrypted_file = self.encrypt(raw_file)

        # todo catch exception
        res = models.execute_kw(
            self.db,
            uid,
            self.password,
            "res.users",
            "upload_encrypted_file",
            [[uid], encrypted_file, row],
        )
        return res

    # given a document id, we should remove the file from the server
    # the corresponding bitmaps row also need to be removed
    def remove(self, fid):
        uid, models = self.connect()
        if not uid:
            raise ValidationError(_("Connection Failed."))
        res = models.execute_kw(
            self.db,
            uid,
            self.password,
            "res.users",
            "remove_encrypted_file_by_ids",
            [[uid], [fid]],
        )
        return res

    # updating old file with the new raw file
    def update(self, fid, new_raw_file):
        uid, models = self.connect()
        if not uid:
            raise ValidationError(_("Connection Failed."))

        keywords = self.extract_keywords(new_raw_file)
        row = self.make_bloom_filter_row(keywords)
        encrypted_file = self.encrypt(new_raw_file)

        res = models.execute_kw(
            self.db,
            uid,
            self.password,
            "res.users",
            "update_file_by_id",
            [[uid], fid, encrypted_file, row],
        )
        return res

    # prepare dpf secrets here and send to each partitions
    # should not send all secrets to central server/master
    def search_keyword(self, keyword):
        uid, models = self.connect()
        if not uid:
            raise ValidationError(_("Connection Failed."))

        res = []
        return res
