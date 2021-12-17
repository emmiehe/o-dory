# O-DORY
O-DORY is a [DORY](https://www.usenix.org/conference/osdi20/presentation/dauterman-dory)-style end-to-end encrypted file-storing application. It allows secure and efficient server-side keyword search and document retrieval without exposing search access patterns. 
Built with [Odoo](https://github.com/odoo/odoo).

# Installation
* prepare a directory
  * `mkdir test-o-dory`
  * `cd test-o-dory`

* get o-dory code
  * `git clone git@github.com:emmiehe/o-dory.git`

* get odoo code
  * If you are only interested in testing out O-DORY, you can install this slightly lighter version of Odoo 15.0:
    * `git clone git@github.com:emmiehe/odoo.git --single-branch`
  * If you want to learn more about Odoo and its source code, please follow the official [installation documentation](https://www.odoo.com/documentation/15.0/administration/install/install.html).

* postgreSQL
  * Odoo uses PostgreSQL as database management system. Use [postgres.app](https://postgresapp.com/) to download and install PostgreSQL (supported version: 10.0 and later). Create a new postgreSQL user either from the GUI or `sudo -u postgres createuser -s $USER`

* dependencies
  * nodejs
    * install [nodejs](https://nodejs.org/en/download/)
    * `sudo npm install -g rtlcss`
  * make sure your Python version is 3.7+
    * create a virtual env: `python3 -m venv odoo-venv-15`
    * `source odoo-venv-15/bin/activate`
    * `pip3 install -r o-dory/requirements.txt`

* run
  * `python3 odoo/odoo-bin --addons-path=odoo/addons,o-dory -d o_dory_server_one -i o_dory_server -p 8898 --limit-time-cpu 7200 --limit-time-real 7200`
    * access server one [here](localhost:8898)
    * login & pw: admin
  * `python3 odoo/odoo-bin --addons-path=odoo/addons,o-dory -d o_dory_server_two -i o_dory_server -p 8899 --limit-time-cpu 7200 --limit-time-real 7200`
    * access server two [here](localhost:8899)
    * login & pw: admin
  * `python3 odoo/odoo-bin --addons-path=odoo/addons,o-dory -d o_dory_client -i o_dory_client -p 8069 --limit-time-cpu 7200 --limit-time-real 7200`
    * access client [here](localhost:8069)
    * login & pw: admin
  * User Alice is automatically created
  * To create more examples, please use the script:
    * `python3 o-dory/scripts/upload_and_search.py bob 100 0.01 10 needle 0 0`
    * This creates Bob's folders on the servers and automatically set up the client side for Bob, and upload load 10 files for Bob.
