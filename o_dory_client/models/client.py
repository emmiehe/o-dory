# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from xmlrpc import client

# import odoo.addons.decimal_precision as dp
import json, random, base64, re, string, hashlib


class ClientManager(models.Model):
    _name = "client.manager"
    _description = "Client Manager"

    name = fields.Char("Name", required=True)
    account_ids = fields.One2many("o.dory.account", "manager_id", "Accounts")

    document_ids = fields.One2many(
        "document.record",
        "manager_id",
        "Document Records",
        help="Records for documents that are uploaded/updated from this client.",
    )

    bloom_filter_k = fields.Integer("Bitmap Width", default=255)  # 1 byte

    def _get_salt(self):
        return "".join(random.choices(string.ascii_uppercase + string.digits, k=20))

    salt = fields.Char("Salt", default=_get_salt)

    # a crude extraction
    def extract_keywords(self, raw_file):
        content = base64.decodebytes(raw_file).decode("utf-8").strip()
        res = re.findall("\w+", content)
        return res

    # todo: implement this seriously
    def compute_word_index(self, word):
        self.ensure_one()
        res = (
            int(hashlib.sha256((word + self.salt).encode()).hexdigest(), 16)
            & self.bloom_filter_k
        )
        print("~~~~~~~~~~~~~~ word: index", word, res)
        return res

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

    # make sure servers are all available
    def verify_connections(self):
        self.ensure_one()
        for account in self.account_ids:
            uid, models = account.connect()
            if not uid:
                raise ValidationError(
                    _(
                        "Connection Test Failed. {}({}):{} ".format(
                            account.url, account.db, models
                        )
                    )
                )
        raise UserError(_("Connections Test Succeeded!"))

    # we only want to verify consistency, but not implement it
    def verify_bitmap_consistency(self):
        self.ensure_one()
        if len(self.account_ids) < 2:
            raise ValidationError(
                _("Consistency verification needs at least two server accounts.")
            )

        versions = [a.retrieve_bitmaps_version() for a in self.account_ids]
        print("bitmaps versions -----> ", versions)
        return all(v == versions[0] for v in versions)

    def upload(self, raw_data):
        self.verify_bitmap_consistency()

        files, rows, filenames = [], [], []
        for rf, filename in raw_data:
            keywords = self.extract_keywords(rf)
            print("--> keywords: ", keywords)
            row = self.make_bloom_filter_row(keywords)
            print("--> bloom filter row: ", row)
            encrypted_file = self.encrypt(rf)
            files.append(encrypted_file)
            rows.append(row)
            filenames.append(filename)

        if not files:
            return []

        data = [files, rows]
        print("-----> data", data)
        res_ids = None
        for account in self.account_ids:
            doc_ids = account.upload(data)
            if res_ids == None:
                res_ids = doc_ids
            if res_ids != doc_ids:
                raise ValidationError(_("Inconsistent uploading."))

        if res_ids != None:
            self.env["document.record"].create(
                [
                    {
                        "manager_id": self.id,
                        "doc_id": res_ids[i],
                        "name": filenames[i],
                    }
                    for i in range(len(res_ids))
                ]
            )

        self.verify_bitmap_consistency()
        return res_ids

    def remove(self, fids):
        self.verify_bitmap_consistency()
        res = False
        for account in self.account_ids:
            res = account.remove(fids)
            if not res:
                raise ValidationError(_("Inconsistent removing."))

        if res:
            rec_ids = self.env["document.record"].search(
                [("manager_id", "=", self.id), ("doc_id", "in", fids)]
            )
            rec_ids.unlink()

        self.verify_bitmap_consistency()
        return res

    # updating old file with the new raw file
    def update(self, fids, new_raw_files):
        self.verify_bitmap_consistency()

        encrypted_files, rows = [], []
        for new_raw_file in new_raw_files:
            keywords = self.extract_keywords(new_raw_file)
            row = self.make_bloom_filter_row(keywords)
            encrypted_file = self.encrypt(new_raw_file)
            encrypted_files.append(encrypted_file)
            rows.append(row)

        res_ids = None
        for account in self.account_ids:
            doc_ids = account.update(fids, encrypted_files, rows)
            if res_ids == None:
                res_ids = doc_ids
            if res_ids != doc_ids:
                raise ValidationError(_("Inconsistent updating."))

        self.verify_bitmap_consistency()
        return res_ids

    def retrieve_ids(self):
        # self.verify_bitmap_consistency()
        ids = set()
        for account in self.account_ids:
            ids = ids.union(set(account.retrieve_ids()))

        if ids:
            oids = self.env["document.record"].search_read(
                [("manager_id", "=", self.id)], fields=["doc_id"]
            )
            oids = [o.get("doc_id") for o in oids]
            nids = [i for i in ids if i not in oids]
            self.env["document.record"].create(
                [{"doc_id": i, "manager_id": self.id, "name": "Unnamed"} for i in nids]
            )
        # self.verify_bitmap_consistency()
        return list(ids)

    # retrieve documents by ids
    def retrieve_files(self, fids):  # a list of fid
        raise ValidationError(_("retrieve files failed"))

    # prepare dpf secrets here and send to each partitions
    # should not send all secrets to central server/master
    def search_keywords(self, keywords):
        self.verify_bitmap_consistency()
        # todo
        indices = [self.compute_word_index(k) for k in keywords]
        print("search indices: ", indices)
        ids = set()
        for account in self.account_ids:
            nids = set(account.search_keywords_indices(indices))
            print("result: ", nids, ids)
            if not ids:
                ids = nids
            elif ids != nids:
                raise ValidationError(
                    _("Inconsistent search possibly due to inconsistent bitmaps")
                )

        self.verify_bitmap_consistency()
        return list(ids)


class ODoryAccount(models.Model):
    _name = "o.dory.account"
    _description = "O-DORY Account"

    manager_id = fields.Many2one(
        "client.manager", ondelete="restrict", string="Client Manager"
    )

    # name = fields.Char("Name") # optional name

    # we need to store user's account information on the o-dory client
    # active = fields.Boolean(string='Active', default=True)
    # oid = fields.Integer(string="O-DORY ID", required=True)
    url = fields.Char(string="O-DORY Server URL", required=True)
    db = fields.Char(
        string="Odoo Server DB",
        required=True,
        help="This is Odoo specific term. Do not confuse this with O-DORY database",
    )
    account = fields.Char(string="O-DORY Account", required=True)
    password = fields.Char(string="O-DORY API Key", required=True)

    # misc for client
    def connect(self):
        self.ensure_one()
        # Logging in
        try:
            common = client.ServerProxy("{}/xmlrpc/2/common".format(self.url))
            uid = common.authenticate(self.db, self.account, self.password, {})
            # getting models
            models = client.ServerProxy("{}/xmlrpc/2/object".format(self.url))
        except client.Error as err:
            return False, err

        return uid, models

    # let the account object handle uploading, removing,
    # and updating (removing and uploading)

    # get the bitmap version from the server
    def retrieve_bitmaps_version(self):
        uid, models = self.connect()
        if not uid:
            raise ValidationError(_("Connection Failed."))
        version = models.execute_kw(
            self.db,
            uid,
            self.password,
            "res.users",
            "get_bitmaps_version",
            [[uid]],
        )
        if version != None:
            return version
        else:
            raise ValidationError(
                _(
                    "Cannot retrieve the bitmap version from server {}({}).".format(
                        self.url, self.db
                    )
                )
            )

    # given raw files, we should upload to a partition
    # (randomly for now as it is out of the scope)
    # we also should add a row to every partition's bitmaps
    # (or we can tell the master and let the master to do it)
    def upload(self, data):
        uid, models = self.connect()
        if not uid:
            raise ValidationError(_("Connection Failed."))

        # todo catch exception
        res_ids = models.execute_kw(
            self.db,
            uid,
            self.password,
            "res.users",
            "upload_encrypted_files",
            [[uid], data],
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

            return res

        return False

    # updating old file with the new raw file
    def update(self, fids, encrypted_files, rows):
        uid, models = self.connect()
        if not uid:
            raise ValidationError(_("Connection Failed."))

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

        # todo, the following should be done from the manager
        # res = [self.decrypt(e) for e in encrypted_documents]
        # should do the auto download thing
        return res

    # prepare dpf secrets here and send to each partitions
    # should not send all secrets to central server/master
    def search_keywords_indices(self, indices):
        uid, models = self.connect()
        if not uid:
            raise ValidationError(_("Connection Failed."))
        res_ids = models.execute_kw(
            self.db,
            uid,
            self.password,
            "res.users",
            "search_documents_by_keyword_indices",
            [[uid], indices],
        )

        return res_ids


class DocumentRecord(models.Model):
    _name = "document.record"
    _description = "Document Record"

    # allow a name field for the customer to map
    name = fields.Char("File Name")
    doc_id = fields.Integer("Document ID", required=True)
    manager_id = fields.Many2one(
        "client.manager",
        ondelete="restrict",
        string="O-DORY Client Manager",
        required=True,
        readonly=True,
    )

    # should removing a document here
    # remove the document stored on the server?
    # maybe that should be a separate action
