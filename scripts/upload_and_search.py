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
    partner_id, user_id, folder_id = None, None, None
    # search if user exists
    partner_ids = models.execute_kw(
        db,
        admin,
        pw,
        "res.partner",
        "search",
        [[["name", "=", username]]],
    )
    if partner_ids:
        partner_id = partner_ids[0]
    else:
        partner_id = models.execute_kw(
            db,
            admin,
            pw,
            "res.partner",
            "create",
            [{"name": username}],
        )

    user_ids = models.execute_kw(
        db,
        admin,
        pw,
        "res.users",
        "search",
        [[["partner_id", "=", partner_id]]],
    )

    if user_ids:
        user_id = user_ids[0]
        logging.info(
            "User {}({}) exists on server {}({})".format(username, user_id, db, url)
        )
    else:
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

    folder_ids = models.execute_kw(
        db,
        admin,
        pw,
        "server.folder",
        "search",
        [[["user_id", "=", user_id]]],
    )

    if folder_ids:
        folder_id = folder_ids[0]
    else:
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

    add_needles = sorted(random.sample(range(doc_num), random.randint(1, doc_num // 2)))
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


def run_test():
    username = "test"
    needle = "needle"
    auto_remove = 1
    rounds = [False, True]

    # creating keyword number steps
    word_nums = [100 * i for i in range(1, 51, 5)]

    # false postive steps
    fps = [0.1, 0.01, 0.001]
    fps = []

    # doc num steps
    doc_nums = [10, 100, 1000]
    doc_nums = []

    results = []

    # some static values
    word, p, doc = 100, 0.1, 100

    for r in rounds:
        word_num_data = []
        for word_num in word_nums:
            bf_width, hash_count = calc_bloom_filter_width_and_hash_count(word_num, p)
            search_time = run(
                username,
                bf_width,
                hash_count,
                word_num,
                doc,
                needle,
                auto_remove,
                r,
            )
            word_num_data.append(search_time)
        if word_nums:
            results.append(
                [
                    word_nums,
                    word_num_data,
                    "word num",
                    "fp 0.01 doc num 100 " + ("seq" if not r else "async"),
                ]
            )

        fp_data = []
        for fp in fps:
            bf_width, hash_count = calc_bloom_filter_width_and_hash_count(word, fp)
            search_time = run(
                username,
                bf_width,
                hash_count,
                word,
                doc,
                needle,
                auto_remove,
                r,
            )
            fp_data.append(search_time)
        if fps:
            results.append(
                [
                    fps,
                    fp_data,
                    "false positive rate",
                    "word num 100 doc num 100 " + ("seq" if not r else "async"),
                ]
            )

        doc_num_data = []
        for doc_num in doc_nums:
            bf_width, hash_count = calc_bloom_filter_width_and_hash_count(word, p)
            search_time = run(
                username,
                bf_width,
                hash_count,
                word,
                doc_num,
                needle,
                auto_remove,
                r,
            )
            doc_num_data.append(search_time)

        if doc_nums:
            results.append(
                [
                    doc_nums,
                    doc_num_data,
                    "doc num",
                    "word num 100 fp 0.01 " + ("seq" if not r else "async"),
                ]
            )

    return results


def lineplot(x_data, y_data, x_label="", y_label="", title=""):
    # Create the plot object
    _, ax = plt.subplots()

    # Plot the best fit line, set the linewidth (lw), color and
    # transparency (alpha) of the line
    for i in range(len(y_data)):
        ax.plot(
            x_data[i],
            y_data[i],
            lw=2,
            color="#%03x" % random.randint(0, 0xFFFFFF),
            alpha=1,
        )

    # Label the axes and provide a title
    ax.set_title(title)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    plt.savefig(title + ".png")


if __name__ == "__main__":
    if len(sys.argv[1:]) == 0:
        results = run_test()
        logging.info("Results: {}".format(results))
        # results = [[[10, 30, 50, 70, 90, 110, 130, 150, 170, 190, 210, 230, 250, 270, 290, 310, 330, 350, 370, 390, 410, 430, 450, 470, 490], [0.4080650806427002, 0.4194481372833252, 0.4803929328918457, 0.555027961730957, 0.5245068073272705, 0.5304629802703857, 0.6047260761260986, 0.6451869010925293, 0.6935012340545654, 0.6320240497589111, 0.7806639671325684, 0.7112410068511963, 0.7591328620910645, 0.7521977424621582, 0.8009989261627197, 0.8078999519348145, 0.7861430644989014, 0.8221099376678467, 0.8917350769042969, 0.8750720024108887, 0.9052841663360596, 1.1183419227600098, 0.9726977348327637, 1.005824089050293, 1.0219829082489014], 'word num', 'fp 0.01 doc num 100 seq'], [[10, 30, 50, 70, 90, 110, 130, 150, 170, 190, 210, 230, 250, 270, 290, 310, 330, 350, 370, 390, 410, 430, 450, 470, 490], [0.32885289192199707, 0.36128807067871094, 0.3885209560394287, 0.41938281059265137, 0.5189428329467773, 0.4790620803833008, 0.5245151519775391, 0.5640840530395508, 0.576624870300293, 0.6404380798339844, 0.640679121017456, 0.6886041164398193, 0.7798347473144531, 0.726431131362915, 0.7810449600219727, 0.7955260276794434, 0.955265998840332, 0.8646731376647949, 0.939215898513794, 1.0636107921600342, 0.9696669578552246, 1.0329458713531494, 1.1084039211273193, 1.0796000957489014, 1.364253044128418], 'word num', 'fp 0.01 doc num 100 async']]
        xs, ys = [], []
        label = ""
        for res in results:
            x, y, label, title = res
            xs.append(x)
            ys.append(y)
            lineplot([x], [y], label, "time", title)
        lineplot(xs, ys, label, "time", "altogether")

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
