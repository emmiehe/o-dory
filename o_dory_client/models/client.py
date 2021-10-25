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
    # oid = fields.Integer(string="O-DORY ID", required=True)
    account = fields.Char(string="O-DORY Account", required=True)
    password = fields.Char(string="O-DORY API Key", required=True)
    url = fields.Char(string="O-DORY Server URL", required=True)
    db = fields.Char(
        string="Odoo Server DB",
        required=True,
        help="This is Odoo specific term. Do not confuse this with O-DORY database",
    )
    bloom_filter_k = fields.Integer("Bitmap Width", default=7)

    document_ids = fields.One2many(
        "document.record",
        "account_id",
        "Document Records",
        help="Records for documents that are uploaded/updated from this client.",
    )

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

    def decrypt(self, encrypted):
        return encrypted

    # let the account object handle uploading, removing,
    # and updating (removing and uploading)

    # given raw files, we should upload to a partition
    # (randomly for now as it is out of the scope)
    # we also should add a row to every partition's bitmaps
    # (or we can tell the master and let the master to do it)
    def upload(self, raw_data):
        uid, models = self.connect()
        if not uid:
            raise ValidationError(_("Connection Failed."))

        files, rows, filenames = [], [], []
        for rf, filename in raw_data:
            keyword = self.extract_keywords(rf)
            row = self.make_bloom_filter_row(keyword)
            encrypted_file = self.encrypt(rf)
            files.append(encrypted_file)
            rows.append(row)
            filenames.append(filename)

        if not files:
            return []

        data = [files, rows]

        # todo catch exception
        res_ids = models.execute_kw(
            self.db,
            uid,
            self.password,
            "res.users",
            "upload_encrypted_files",
            [[uid], data],
        )

        if res_ids != None:
            self.env["document.record"].create(
                [
                    {
                        "account_id": self.id,
                        "doc_id": res_ids[i],
                        "name": filenames[i],
                    }
                    for i in range(len(res_ids))
                ]
            )

        return res_ids

    # given document ids, we should remove the file from the server
    # the corresponding bitmaps row also need to be removed
    def remove(self, fids):
        uid, models = self.connect()
        if not uid:
            raise ValidationError(_("Connection Failed."))
        if fids:
            res = models.execute_kw(
                self.db,
                uid,
                self.password,
                "res.users",
                "remove_encrypted_files_by_ids",
                [[uid], fids],
            )

            if res:
                rec_ids = self.env["document.record"].search(
                    [("account_id", "=", self.id), ("doc_id", "in", fids)]
                )
                rec_ids.unlink()
            return res

        return False

    # updating old file with the new raw file
    def update(self, fids, new_raw_files):
        uid, models = self.connect()
        if not uid:
            raise ValidationError(_("Connection Failed."))

        encrypted_files, rows = [], []
        for new_raw_file in new_raw_files:
            keywords = self.extract_keywords(new_raw_file)
            row = self.make_bloom_filter_row(keywords)
            encrypted_file = self.encrypt(new_raw_file)
            encrypted_files.append(encrypted_file)
            rows.append(row)

        res = models.execute_kw(
            self.db,
            uid,
            self.password,
            "res.users",
            "update_files_by_ids",
            [[uid], [fids, encrypted_files, rows]],
        )
        return res

    def retrieve_ids(self):
        uid, models = self.connect()
        if not uid:
            raise ValidationError(_("Connection Failed."))

        ids = models.execute_kw(
            self.db,
            uid,
            self.password,
            "res.users",
            "retrieve_doc_ids",
            [[uid]],
        )

        if ids:
            oids = self.env["document.record"].search_read(
                [("account_id", "=", self.id)], fields=["doc_id"]
            )
            oids = [o.get("doc_id") for o in oids]
            nids = [i for i in ids if i not in oids]
            self.env["document.record"].create(
                [{"doc_id": i, "account_id": self.id, "name": "Unnamed"} for i in nids]
            )

        return ids

    # retrive documents by ids
    def retrieve_files(self, fids):  # a list of fid
        uid, models = self.connect()
        if not uid:
            raise ValidationError(_("Connection Failed."))

        encrypted_documents = models.execute_kw(
            self.db,
            uid,
            self.password,
            "res.users",
            "retrieve_encrypted_files_by_ids",
            [[uid], fids],
        )

        res = [self.decrypt(e) for e in encrypted_documents]

        # todo
        # should do the auto download thing
        return res

    # prepare dpf secrets here and send to each partitions
    # should not send all secrets to central server/master
    def search_keyword(self, keyword):
        uid, models = self.connect()
        if not uid:
            raise ValidationError(_("Connection Failed."))

        res = []
        return res


class DocumentRecord(models.Model):
    _name = "document.record"
    _description = "Document Record"

    # allow a name field for the customer to map
    name = fields.Char("File Name")
    doc_id = fields.Integer("Document ID", required=True)
    account_id = fields.Many2one(
        "o.dory.account",
        ondelete="restrict",
        string="O-DORY Account",
        required=True,
        readonly=True,
    )

    # should removing a document here
    # remove the document stored on the server?
    # maybe that should be a separate action
