import sys, logging, base64, random, string, math, time
from xmlrpc import client
import matplotlib.pyplot as plt
import numpy as np

# client
URL = "http://127.0.0.1:8069"
DB = "o_dory_client"
USER = "admin"
PW = "admin"

# server one
URL_SERVER_ONE = "http://localhost:8898"
DB_SERVER_ONE = "o_dory_server_one"
ADMIN_ONE = "admin"
ADMIN_ONE_PW = "admin"

# server two
URL_SERVER_TWO = "http://localhost:8899"
DB_SERVER_TWO = "o_dory_server_two"
ADMIN_TWO = "admin"
ADMIN_TWO_PW = "admin"


logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%I:%M:%S %p",
)

# mute matplotlib debug msgs
logging.getLogger("matplotlib.font_manager").setLevel(logging.WARNING)

# n is the amount of keywords we expect to have
# p is the false positive rate range (0, 1) that is acceptable
# m is the bloom filter width (num of bits)
# k is the hash count
def calc_bloom_filter_width_and_hash_count(n, p):
    m = round(-n * math.log(p) / (math.log(2) ** 2))
    k = round(m / n * math.log(2))
    return m if m else 1, k if k else 1


def login_and_verify_access(url, db, username, password, target_models=[]):
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


def create_user_server(url, db, login, pw, username):
    admin, models = login_and_verify_access(url, db, login, pw)
    
    partner_id = models.execute_kw(
        db,
        admin,
        pw,
        "res.partner",
        "create",
        [{"name": username}],
    )
    
    user_id = models.execute_kw(
        db,
        admin,
        pw,
        "res.users",
        "create",
        [{"login": username, "password": username, "partner_id": partner_id}],
    )
    logging.info(
        "Created {}({}) on server {}({})".format(username, user_id, db, url)
    )

    folder_id = models.execute_kw(
        db,
        admin,
        pw,
        "server.folder",
        "create",
        [{"user_id": user_id, "name": username}],
    )

    return partner_id, user_id, folder_id


def remove_user_server(url, db, login, pw, ids):
    partner_id, user_id, folder_id = ids
    admin, models = login_and_verify_access(url, db, login, pw)
    models.execute_kw(
        db,
        admin,
        pw,
        "server.folder",
        "unlink",
        [folder_id],
    )
    models.execute_kw(
        db,
        admin,
        pw,
        "res.users",
        "unlink",
        [user_id],
    )
    models.execute_kw(
        db,
        admin,
        pw,
        "res.partner",
        "unlink",
        [partner_id],
    )
    logging.info(
        "Removed user {}({}) from server {}({})".format(user_id, folder_id, db, url)
    )


def create_users_server(username):
    user1_ids = create_user_server(
        URL_SERVER_ONE, DB_SERVER_ONE, ADMIN_ONE, ADMIN_ONE_PW, username
    )
    user2_ids = create_user_server(
        URL_SERVER_TWO, DB_SERVER_TWO, ADMIN_TWO, ADMIN_TWO_PW, username
    )
    return user1_ids, user2_ids


def remove_users_server(user_ids):
    assert len(user_ids) == 2
    remove_user_server(
        URL_SERVER_ONE, DB_SERVER_ONE, ADMIN_ONE, ADMIN_ONE_PW, user_ids[0]
    )
    remove_user_server(
        URL_SERVER_TWO, DB_SERVER_TWO, ADMIN_TWO, ADMIN_TWO_PW, user_ids[1]
    )


def create_client_manager(url, db, login, pw, client_params):
    username, bloom_filter_width, hash_count, salt, async_enabled = client_params
    uid, models = login_and_verify_access(url, db, login, pw)
    manager_id = models.execute_kw(
        db,
        uid,
        pw,
        "client.manager",
        "create",
        [
            {
                "name": username,
                "bloom_filter_width": bloom_filter_width,
                "hash_count": hash_count,
                "salt": salt,
                "async_enabled": async_enabled,
            }
        ],
    )
    logging.info("Created client manager {}({})".format(username, manager_id))

    models.execute_kw(
        db,
        uid,
        pw,
        "o.dory.account",
        "create",
        [
            {
                "account": username,
                "password": username,
                "url": URL_SERVER_ONE,
                "db": DB_SERVER_ONE,
                "manager_id": manager_id,
            },
        ],
    )
    models.execute_kw(
        db,
        uid,
        pw,
        "o.dory.account",
        "create",
        [
            {
                "account": username,
                "password": username,
                "url": URL_SERVER_TWO,
                "db": DB_SERVER_TWO,
                "manager_id": manager_id,
            },
        ],
    )

    return uid, models, manager_id


def remove_client_manager(url, db, login, pw, manager_id):
    uid, models = login_and_verify_access(url, db, login, pw)
    models.execute_kw(
        db,
        uid,
        pw,
        "client.manager",
        "unlink",
        [manager_id],
    )
    logging.info("Removed client manager {}".format(manager_id))


def prepare_doc_data(word_num, doc_num, needle):

    words = [
        "".join(random.choices(string.ascii_uppercase + string.digits, k=10))
        for i in range(word_num)
    ]

    msgs = [
        " ".join(random.sample(words, random.randint(1, len(words))))
        for i in range(doc_num)
    ]

    add_needles = sorted(
        random.sample(range(doc_num), random.randint(1, max(doc_num // 2, 1)))
    )
    for i in add_needles:
        msgs[i] = msgs[i] + " " + needle

    logging.info(
        "Generating {} keywords, needle is '{}', {}".format(
            word_num, needle, add_needles
        )
    )

    data = []

    for i, msg in enumerate(msgs):
        data.append(
            [
                0,
                0,
                {
                    "raw_file": base64.b64encode(msg.encode()).decode(),
                    "filename": needle
                    if i in add_needles
                    else "No {} here".format(needle),
                },
            ]
        )
    return data


def run(
    name, bf_width, hash_count, word_num, doc_num, needle, auto_remove, async_enabled
):
    logging.info(
        "\n"
        "\t username: {}\n"
        "\t bloom filter width: {}\n"
        "\t hash count: {}\n"
        "\t keyword count: {}\n"
        "\t document count: {}\n"
        "\t needle: {}\n"
        "\t autoremove: {}\n"
        "\t async enabled: {}\n".format(
            name,
            bf_width,
            hash_count,
            word_num,
            doc_num,
            needle,
            auto_remove,
            async_enabled,
        )
    )

    url, db, username, password = URL, DB, USER, PW

    user = name + "@o-dory.com"
    search_time = 0

    try:

        user_ids = create_users_server(user)
        user1_ids, user2_ids = user_ids
        try:
            client_data = [user, bf_width, hash_count, user, async_enabled]
            uid, models, manager_id = create_client_manager(
                url, db, username, password, client_data
            )

            ### uploading & searching
            search_res = set()
            try:
                data = prepare_doc_data(word_num, doc_num, needle)
                logging.info(
                    "Uploading {} documents with upload wizard".format(doc_num)
                )

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
                    db,
                    uid,
                    password,
                    "client.wizard",
                    "action_do_upload",
                    [wizard_upload_id],
                )

                search_data = [[0, 0, {"search_term": needle}]]

                logging.info(
                    "Searching keyword '{}' over all documents with search wizard".format(
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

                start = time.time()
                models.execute_kw(
                    db,
                    uid,
                    password,
                    "client.wizard",
                    "action_do_search",
                    [wizard_search_id],
                )
                end = time.time()
                search_time = end - start
                logging.info("Search time: {}".format(search_time))

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
                logging.error("Error during uploading/searching: {}".format(e))

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

            expected_result = [
                doc_id.get("doc_id")
                for doc_id in doc_ids
                if doc_id.get("name") == needle
            ]
            logging.info("Expected result: {}".format(expected_result))

            expected_res = set(expected_result)

            assert(search_res.intersection(expected_res) == expected_res)
            logging.info("Search result passed")
            
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
                    db,
                    uid,
                    password,
                    "client.wizard",
                    "action_do_remove",
                    [wizard_remove_id],
                )

                remove_client_manager(url, db, username, password, manager_id)
        except Exception as e:
            logging.error("Error creating client manager: {}".format(e))

        if auto_remove:
            remove_users_server(user_ids)

    except Exception as e:
        logging.error("Error creating user on the servers: {}".format(e))

    logging.info("Done")
    return search_time


def plot_data(word_nums, fps, doc_nums, r, username, needle, auto_remove):
    data = []
    for word_num in word_nums:
        for fp in fps:
            for doc_num in doc_nums:
                bf_width, hash_count = calc_bloom_filter_width_and_hash_count(
                    word_num, fp
                )
                search_time = run(
                    username,
                    bf_width,
                    hash_count,
                    word_num,
                    doc_num,
                    needle,
                    auto_remove,
                    r,
                )
                data.append(search_time)
    return data


def run_test():
    username = "test"
    needle = "needle"
    auto_remove = 1
    rounds = [False]

    # creating keyword number steps
    word_nums = [2 ** i for i in range(13)]

    # false postive steps
    fps = [0.0001, 0.001, 0.01, 0.1]

    # doc num steps
    doc_nums = [2 ** i for i in range(13)]

    results = []

    # some static values
    word, p, doc = 1024, 0.01, 1024

    word_num_data = [
        [
            word_nums,
            plot_data(word_nums, [p], [doc], r, username, needle, auto_remove),
            "word_num",
            "fp 0.01 doc num 100 " + ("seq" if not r else "async"),
        ]
        for r in rounds
    ]

    fp_data = [
        [
            fps,
            plot_data([word], fps, [doc], r, username, needle, auto_remove),
            "false positive rate",
            "word num 100 doc num 100 " + ("seq" if not r else "async"),
        ]
        for r in rounds
    ]

    doc_num_data = [
        [
            doc_nums,
            plot_data([word], [p], doc_nums, r, username, needle, auto_remove),
            "doc num",
            "word num 100 fp 0.01 " + ("seq" if not r else "async"),
        ]
        for r in rounds
    ]

    return word_num_data, fp_data, doc_num_data


def lineplot(x_data, y_data, x_label="", y_label="", title=""):
    # Create the plot object
    _, ax = plt.subplots()

    # Plot the best fit line, set the linewidth (lw), color and
    # transparency (alpha) of the line

    ax.plot(
        x_data[0],
        y_data[0],
        label="SEQ",
        lw=2,
        color="b",
        alpha=1,
    )

    # ax.plot(
    #     x_data[1],
    #     y_data[1],
    #     label="ASYNC",
    #     lw=2,
    #     color="g",
    #     alpha=1,
    # )

    # Label the axes and provide a title
    ax.set_title(title)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.legend()
    plt.savefig(title + ".png")


if __name__ == "__main__":
    if len(sys.argv[1:]) == 0:
        results = run_test()
        logging.info("Results: {}".format(results))
        for result in results:
            r0 = result[0]
            lineplot([r0[0]], [r0[1]], r0[2], "time", r0[3])
            # r0, r1 = result
            # lineplot([r0[0], r1[0]], [r0[1], r1[1]], r0[2], "time", r0[3])

        sys.exit()
    elif 0 < len(sys.argv[1:]) < 7:
        print(
            "input: <username str> <keyword_num int> <false_positive_rate float> <document_num int> <needle str> <auto_remove int> <async int>\n"
            "ex: bob 100 0.1 100 needle 1 0"
        )
        sys.exit()

    username = sys.argv[1]
    word_num = int(sys.argv[2])
    p = float(sys.argv[3])
    doc_num = int(sys.argv[4])
    needle = sys.argv[5]
    auto_remove = int(sys.argv[6])
    async_enabled = True if int(sys.argv[7]) > 0 else False
    assert word_num > 0 and 0 < p < 1 and doc_num > 0
    bf_width, hash_count = calc_bloom_filter_width_and_hash_count(word_num, p)

    run(
        username,
        bf_width,
        hash_count,
        word_num,
        doc_num,
        needle,
        auto_remove,
        async_enabled,
    )
