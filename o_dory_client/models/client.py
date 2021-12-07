# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from xmlrpc import client

# import odoo.addons.decimal_precision as dp
import mmh3
import numpy as np
import sycret, random
import random, base64, re, string, hashlib
import ujson as json

eq = sycret.EqFactory(n_threads=10)


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

    bloom_filter_k = fields.Integer(
        "Bitmap Width", default=1000
    )  # this is actually bloom_filter width
    hash_count = fields.Integer("Hash Count", default=7)

    def _get_salt(self):
        return "".join(random.choices(string.ascii_uppercase + string.digits, k=20))

    salt = fields.Char("Salt", default=_get_salt)

    # a crude extraction
    def extract_keywords(self, raw_file):
        content = base64.decodebytes(raw_file).decode("utf-8").strip()
        res = re.findall("\w+", content)
        return res

    def hash_word_to_indices(self, word):
        self.ensure_one()
        return [
            mmh3.hash(word + self.salt, seed) % self.bloom_filter_k
            for seed in range(self.hash_count)
        ]

    def compute_word_indices(self, word):
        self.ensure_one()
        indices = self.hash_word_to_indices(word)
        return sorted(list(set(indices)))

    def generate_doc_version(self):
        return "".join(random.choices(string.ascii_uppercase + string.digits, k=12))

    def get_mask_from_doc_version(self, version):
        self.ensure_one()
        mask = bin(int(hashlib.sha256((version + self.salt).encode()).hexdigest(), 16))[
            2 : 2 + self.bloom_filter_k
        ]
        mask = [int(m) for m in mask]
        while len(mask) < self.bloom_filter_k:
            mask.extend(mask)
        # fake mask
        # mask = [0 for i in range(self.bloom_filter_k)]
        print("~~~~ get mask from doc version:", version, mask)
        return mask[:self.bloom_filter_k]

    def make_bloom_filter_row(self, keywords):
        self.ensure_one()
        res = [0] * self.bloom_filter_k
        for keyword in keywords:
            indices = self.compute_word_indices(keyword)
            for i in indices:
                res[i] = 1
        return res

    # mask the given bloom filter with the given version
    def mask_bloom_filter_row(self, bf_row, version):
        mask = self.get_mask_from_doc_version(version)
        curr = 0
        print("pre MASK:", bf_row)
        for i in range(len(bf_row)):
            if curr >= len(mask):
                curr = 0
            bf_row[i] ^= mask[curr]
            curr += 1
        print("post MASK:", bf_row)
        return version

    def generate_mac(self, bit, index, doc_version):
        self.ensure_one()
        mac = (
            int(
                hashlib.sha256(
                    (str(bit) + str(index) + doc_version + self.salt).encode()
                ).hexdigest(),
                16,
            )
            % 256
        )
        return mac

    def generate_macs(self, bf_row, doc_version):
        # given a (masked) bf_row
        # generate an array of macs
        self.ensure_one()
        res = []
        for i in range(self.bloom_filter_k):
            # salt is per client manager (so effectively per folder)
            mac = self.generate_mac(bf_row[i], i, doc_version)
            res.append(mac)
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
        # print("bitmaps versions -----> ", versions)
        if not all(v == versions[0] for v in versions):
            raise ValidationError(_("bitmaps versions don't match"))

    def verify_and_retrieve_current_macs(self):
        self.ensure_one()
        old_macs_lst = [account.retrieve_col_macs() for account in self.account_ids]
        if not all(om == old_macs_lst[0] for om in old_macs_lst):
            raise ValidationError(_("MACs don't match"))

        old_macs = old_macs_lst[0]
        if not old_macs:
            return [0 for i in range(self.bloom_filter_k)]

        return old_macs

    def verify_and_compute_macs_for_doc_ids(self, doc_ids):
        macs = [
            account.compute_macs_for_doc_ids(doc_ids) for account in self.account_ids
        ]
        if not all(m == macs[0] for m in macs):
            raise ValidationError(_("Selected computed MACs don't match"))
        return macs[0]

    def update_col_macs(self, old_macs, new_macs):
        self.ensure_one()
        print("update col macs", old_macs, new_macs)
        new_macs = [old_macs[i] ^ new_macs[i] for i in range(self.bloom_filter_k)]
        # macs needs to be serialized
        updated_macs = json.dumps(new_macs)
        return updated_macs

    def get_doc_count(self):
        self.ensure_one()
        if len(self.account_ids) < 2:
            raise ValidationError(
                _("Consistency verification needs at least two server accounts.")
            )

        counts = [a.retrieve_doc_count() for a in self.account_ids]
        print("counts -----> ", counts)
        if not all(c == counts[0] for c in counts):
            raise ValidationError(_("Inconsistent doc counts."))
        return counts[0]

    def upload(self, raw_data):
        self.verify_bitmap_consistency()

        old_macs = self.verify_and_retrieve_current_macs()

        files, rows, filenames, macs = [], [], [], []
        for rf, filename in raw_data:
            keywords = self.extract_keywords(rf)
            # print("--> keywords: ", keywords)
            row = self.make_bloom_filter_row(keywords)
            version = self.generate_doc_version()
            self.mask_bloom_filter_row(row, version)
            mac = self.generate_macs(row, version)
            if not macs:
                macs = mac
            else:
                macs = [macs[i] ^ mac[i] for i in range(len(mac))]
            # print("--> bloom filter row: ", row)
            encrypted_file = self.encrypt(rf)
            files.append([encrypted_file, version])
            rows.append(row)
            filenames.append(filename)

        if not files:
            return []

        macs = self.update_col_macs(old_macs, macs)

        data = [files, rows, macs]
        # print("-----> data", data)
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
        old_macs = self.verify_and_retrieve_current_macs()
        # compute selected files macs
        new_macs = self.verify_and_compute_macs_for_doc_ids(fids)
        macs = self.update_col_macs(old_macs, new_macs)

        for account in self.account_ids:
            res = account.remove([fids, macs])
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
        old_macs = self.verify_and_retrieve_current_macs()

        encrypted_files, rows, macs = [], [], []
        for new_raw_file in new_raw_files:
            keywords = self.extract_keywords(new_raw_file)
            row = self.make_bloom_filter_row(keywords)
            version = self.generate_doc_version()
            self.mask_bloom_filter_row(row, version)
            mac = self.generate_macs(row, version)
            if not macs:
                macs = mac
            else:
                macs = [macs[i] ^ mac[i] for i in range(len(mac))]

            encrypted_file = self.encrypt(new_raw_file)
            encrypted_files.append([encrypted_file, version])
            rows.append(row)

        res_ids = None
        remove_macs = self.verify_and_compute_macs_for_doc_ids(fids)
        macs = [remove_macs[i] ^ macs[i] for i in range(len(macs))]
        macs = self.update_col_macs(old_macs, macs)
        data = [fids, encrypted_files, rows, macs]
        for account in self.account_ids:
            doc_ids = account.update(data)
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

    def prepare_dpf(self, target_indices):
        self.verify_bitmap_consistency()
        doc_num = self.get_doc_count()
        # the idea is that we want dpf for every column
        # the end results should be two chunks
        a, b = [], []
        # slightly worried about perf
        for i in range(self.bloom_filter_k):
            keys_a, keys_b = eq.keygen(doc_num)
            # Reshape to a C-contiguous array (necessary for from_buffer)
            alpha = eq.alpha(keys_a, keys_b)
            x = alpha.astype(np.int32)

            # change non-target columns to 0
            if i not in target_indices:
                for k in range(doc_num):
                    r = random.randint(-100, 100)
                    x[k] += r if r else 10  # avoid not adding anything

            # print(x)
            x = x.tolist()
            a.append([x, keys_a.tolist()])
            b.append([x.copy(), keys_b.tolist()])

        print("=== SHAPE ", len(a), len(a[0]), len(a[0][1]), len(a[0][1][0]))

        self.verify_bitmap_consistency()
        return a, b

    # prepare dpf secrets here and send to each partitions
    # should not send all secrets to central server/master
    def search_keywords(self, keywords):
        self.verify_bitmap_consistency()
        if len(self.account_ids) != 2:
            raise ValidationError(_("Need exactly two servers for searching."))

        server_macs = self.verify_and_retrieve_current_macs()

        # todo: for now only consider keywords is a list of one element
        # due to the wizard/frontend setup this is actually true
        assert len(keywords) == 1
        indices = self.compute_word_indices(keywords[0])

        print("keywords: indices ", keywords, indices)

        a, b = self.prepare_dpf(indices)
        account_a, account_b = self.account_ids[0], self.account_ids[1]
        search_data_a = account_a.search_keywords(0, json.dumps(a))
        search_data_b = account_b.search_keywords(1, json.dumps(b))

        rs_a, row_to_doc, doc_versions = json.loads(search_data_a)
        rs_b, __, __ = json.loads(search_data_b)
        # print(rs_a)
        # print(rs_b)
        # combining results
        results = []
        for i, ra in enumerate(rs_a):
            rb = rs_b[i]
            # In PySyft, the AdditiveSharingTensor class will take care of the modulo
            res = []
            for j, r_a in enumerate(ra):
                r_b = rb[j]
                res.append(r_a ^ r_b)
                # res.append((r_a + r_b) % (2 ** (eq.N * 8)))
            results.append(res)
        # todo: need to do the doc conversion
        # conveniently, the only valid columns are the indexed columns
        results = [col for (i, col) in enumerate(results) if i in indices]

        print("filtered results ", results)
        row_to_doc = {int(k): int(v) for (k, v) in row_to_doc}

        # versions
        versions = {e.get("id"): e.get("version") for e in doc_versions}
        # now we need to check if the returned columns match our macs
        for col, i in enumerate(indices):
            macs = [
                self.generate_mac(
                    results[col][row], i, versions.get(row_to_doc.get(row))
                )
                for row in range(len(results[col]))
            ]
            print("col macs", macs)
            m = None
            for mac in macs:
                if m == None:
                    m = mac
                else:
                    m ^= mac
            print("comparing mac", m, server_macs[i])
            if m != server_macs[i]:
                raise ValidationError(_("MACs don't match. Server could be corrupted."))

        print("row to doc ", row_to_doc)
        print("versions ", versions)
        # i is row
        rows = []
        for i in range(len(results[0])):
            version = versions.get(row_to_doc.get(i))
            mask = self.get_mask_from_doc_version(version)
            mask = [mask[m] for m in indices]
            print("selected mask ", mask)
            unmasked = [results[k][i] ^ mask[k] for k in range(len(results))]
            print("unmasked ", unmasked)
            # if all([results[k][i] for k in range(len(results))]):
            if all(unmasked):
                rows.append(i)

        # print(rows)
        docs = []
        for row in rows:
            docs.append(row_to_doc.get(row))

        self.verify_bitmap_consistency()
        print("----------------- done searching from server", docs)
        return docs

    # the naive model will just send the indices to the server
    def search_keywords_naive(self, keywords):
        self.verify_bitmap_consistency()
        # todo
        indices = []
        for keyword in keywords:
            indices.append(self.compute_word_indices(keyword))

        # print("search indices: ", indices)
        ids = set()
        for account in self.account_ids:
            lst = [tuple(sorted(e)) for e in account.search_keywords_indices(indices)]
            nids = set(lst)
            # print("result: ", nids, ids)
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

    def retrieve_doc_count(self):
        uid, models = self.connect()
        if not uid:
            raise ValidationError(_("Connection Failed."))
        count = models.execute_kw(
            self.db,
            uid,
            self.password,
            "res.users",
            "get_indexed_document_count",
            [[uid]],
        )
        return count

    def retrieve_col_macs(self):
        uid, models = self.connect()
        if not uid:
            raise ValidationError(_("Connection Failed."))

        col_macs_json = models.execute_kw(
            self.db, uid, self.password, "res.users", "retrieve_col_macs", [[uid]]
        )
        print(col_macs_json)
        if not col_macs_json:
            return [0 for i in range(self.manager_id.bloom_filter_k)]
        col_macs = json.loads(col_macs_json)
        return col_macs

    def compute_macs_for_doc_ids(self, doc_ids):
        uid, models = self.connect()
        if not uid:
            raise ValidationError(_("Connection Failed."))

        serialized_bitmaps_doc_versions = models.execute_kw(
            self.db,
            uid,
            self.password,
            "res.users",
            "get_bitmaps_doc_versions_by_doc_ids",
            [[uid], doc_ids],
        )
        bitmaps_doc_versions = json.loads(serialized_bitmaps_doc_versions)
        macs_lst = [
            self.manager_id.generate_macs(bitmap, version)
            for (bitmap, version) in bitmaps_doc_versions
        ]
        macs = []
        for m in macs_lst:
            if not macs:
                macs = m
            else:
                macs = [macs[i] ^ m[i] for i in range(len(m))]
        print("compute macs for doc ids", macs)
        return macs

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
    def remove(self, data):
        if not data:
            return False

        uid, models = self.connect()
        if not uid:
            raise ValidationError(_("Connection Failed."))

        res = models.execute_kw(
            self.db,
            uid,
            self.password,
            "res.users",
            "remove_encrypted_files_by_ids",
            [[uid], data],
        )

        return res

    # updating old file with the new raw file
    def update(self, data):
        fids, encrypted_files, rows, new_macs = data
        if not fids or not (len(fids) == len(encrypted_files) == len(rows)):
            return False

        uid, models = self.connect()
        if not uid:
            raise ValidationError(_("Connection Failed."))

        res = models.execute_kw(
            self.db,
            uid,
            self.password,
            "res.users",
            "update_files_by_ids",
            [[uid], data],
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

    # retrieve documents by ids
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

    # prepare dpf secrets here and send to each partitions
    # should not send all secrets to central server/master
    def search_keywords(self, y, secrets):
        uid, models = self.connect()
        if not uid:
            raise ValidationError(_("Connection Failed."))
        res_ids = models.execute_kw(
            self.db,
            uid,
            self.password,
            "res.users",
            "server_search",
            [[uid], y, secrets],
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
