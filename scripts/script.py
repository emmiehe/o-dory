import sys, logging, base64, random, string
from xmlrpc import client

URL = "http://127.0.0.1:8069"
DB = "o_dory_client"
USER = "admin"
PW = "admin"

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%I:%M:%S %p",
)


def login_and_verify_access(url, db, username, password, target_models):
    # Logging in
    common = client.ServerProxy("{}/xmlrpc/2/common".format(url))
    # print(common.version())
    uid = common.authenticate(db, username, password, {})
    # getting models
    models = client.ServerProxy("{}/xmlrpc/2/object".format(url))

    for t_model in target_models:
        can_read_model = models.execute_kw(
            db,
            uid,
            password,
            t_model,
            "check_access_rights",
            ["write"],
            {"raise_exception": False},
        )
        if not can_read_model:
            logging.error(
                "User {} do not have access right to {} model".format(username, t_model)
            )
            sys.exit()

    return uid, models


def run():
    url, db, username, password = URL, DB, USER, PW
    target_models = [
        "client.wizard",
        "client.data.wizard",
    ]
    uid, models = login_and_verify_access(url, db, username, password, target_models)
    manager_id = models.execute_kw(
        db,
        uid,
        password,
        "client.manager",
        "search",
        [[("name", "=", "Alice")]],
    )

    manager_id = manager_id[0]
    doc_num = 20
    msgs = [
        "".join(random.choices(string.ascii_uppercase + string.digits, k=10))
        for i in range(doc_num)
    ]
    data = []
    search_data = []
    for msg in msgs:
        data.append(
            [
                0,
                0,
                {"raw_file": base64.b64encode(msg.encode()).decode(), "filename": msg},
            ]
        )
        search_data.append([0, 0, {"search_term": msg}])

    logging.info("Uploading {} documents with upload wizard".format(doc_num))

    wizard_upload_id = models.execute_kw(
        db,
        uid,
        password,
        "client.wizard",
        "create",
        [
            {
                "manager_id": manager_id,
                "data_ids": data,
            }
        ],
    )

    models.execute_kw(
        db, uid, password, "client.wizard", "action_do_upload", [wizard_upload_id]
    )

    logging.info("Searching all documents with search wizard")

    wizard_search_id = models.execute_kw(
        db,
        uid,
        password,
        "client.wizard",
        "create",
        [
            {
                "manager_id": manager_id,
                "data_ids": search_data,
            }
        ],
    )

    models.execute_kw(
        db, uid, password, "client.wizard", "action_do_search", [wizard_search_id]
    )

    res = models.execute_kw(
        db,
        uid,
        password,
        "client.data.wizard",
        "search_read",
        [[["wizard_id", "=", wizard_search_id]]],
        {"fields": ["search_result"]},
    )

    logging.info("Search result {}".format(res))

    logging.info("Removing all documents")

    doc_ids = models.execute_kw(
        db,
        uid,
        password,
        "document.record",
        "search_read",
        [[["manager_id", "=", manager_id]]],
        {"fields": ["doc_id"]},
    )

    delete_data = []
    for doc in doc_ids:
        delete_data.append([0, 0, {"document_id": int(doc.get("doc_id"))}])

    wizard_remove_id = models.execute_kw(
        db,
        uid,
        password,
        "client.wizard",
        "create",
        [
            {
                "manager_id": manager_id,
                "data_ids": delete_data,
            }
        ],
    )

    models.execute_kw(
        db, uid, password, "client.wizard", "action_do_remove", [wizard_remove_id]
    )

    logging.info("Done")


if __name__ == "__main__":
    run()
