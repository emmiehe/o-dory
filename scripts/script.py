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


def run(doc_num, needle, auto_remove=1):
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
    search_res = set()

    try:
        word_num = 100
        words = ["".join(random.choices(string.ascii_uppercase + string.digits, k=10))
            for i in range(word_num)]
        
        msgs = [
            " ".join(random.sample(words, random.randint(1, len(words))))
            for i in range(doc_num)
        ]

        add_needles = sorted(random.sample(range(doc_num), random.randint(1, doc_num//2)))
        for i in add_needles:
            msgs[i] = msgs[i] + " " + needle

        logging.info("Generating {} keywords, needle is {}, {}".format(word_num, needle, add_needles))
        
        data = []

        for i, msg in enumerate(msgs):
            data.append(
                [
                    0,
                    0,
                    {
                        "raw_file": base64.b64encode(msg.encode()).decode(),
                        "filename": needle if i in add_needles else "No needle here",
                    },
                ]
            )
            
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

        search_data = [[0, 0, {"search_term": needle}]]
        
        logging.info(
            "Searching keyword {} over all documents with search wizard".format(
                search_data[0][2].get("search_term")
            )
        )

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

        search_result = res[0].get("search_result")
        search_result = [int(e) for e in search_result[1:-1].split(",")]

        search_res = set(search_result)
        logging.info("Search result: {}".format(search_result))

    except Exception as e:
        logging.error("Error during uploading/searching: {}", e)
        pass

    doc_ids = models.execute_kw(
        db,
        uid,
        password,
        "document.record",
        "search_read",
        [[["manager_id", "=", manager_id]]],
        {"fields": ["doc_id", "name"]},
    )
    
    # for doc_id in doc_ids:
    #     logging.info("{}:{}".format(doc_id.get("doc_id"), doc_id.get("name")))

    expected_result = [doc_id.get("doc_id") for doc_id in doc_ids if doc_id.get("name") == needle]
    logging.info("Expected result: {}".format(expected_result))
    
    expected_res = set(expected_result)

    if search_res.intersection(expected_res) == expected_res:
        logging.info("Search result passed")
    else:
        logging.error("False results")

    if auto_remove:
    
        delete_data = []
        for doc in doc_ids:
            delete_data.append([0, 0, {"document_id": int(doc.get("doc_id"))}])

        logging.info("Removing all documents")
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
    if len(sys.argv[1:]) < 2:
        print("input: <doc_num> <needle str>")
        sys.exit()

    doc_num = int(sys.argv[1])
    needle = sys.argv[2]
    run(doc_num, needle, 1)
