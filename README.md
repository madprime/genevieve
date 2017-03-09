# Genevieve

Genevieve client: retrieve Open Humans genome data and, using GenNotes, report
ClinVar matches &amp; add consensus notes.

## Notes on reusability

Genevieve has been adapted for a specific Open Humans integration: users are
expected to log in via their Open Humans account and authorize Genevieve's
project within Open Humans.

This limits its reusability, but the source of Genevieve is shared to enable
alternate approaches.

The underlying database Genevieve draws upon and edits is GenNotes:
https://github.com/OpenHumans/gennotes

Because GenNotes is decoupled from Genevieve, alternate versions of this
project could be created that accept genetic data in a different manner (e.g.
via direct upload) and retrieve variant information from the same GenNotes
database.

Please check with Madeleine Ball before using the term "Genevieve" to describe
an alternate version of this app.

## Local installation/development set-up

### Dependencies

- Python 3.5.1
- postgres (`apt-get install libpq-dev python-dev` and
  `apt-get install postgresql postgresql-contrib` in Debian/Ubuntu)
- RabbitMQ (`apt-get install rabbitmq-server` in Debian/Ubuntu)
   - Ubuntu should automatically start the server, but in case that doesn't happen: You can stop the server with `sudo rabbitmqctl stop` and start it running in the background with `sudo rabbitmq-server --detached`.

### Set up the PostgreSQL database

- In Debian/Ubuntu
  - Become the postgres user: `sudo su - postgres`
  - Create a database (example name 'mydb'): `createdb mydb`
  - Create a user (example user 'jdoe'): `createuser -P jdoe`
  - Enter the password at prompt (example password: 'pa55wd')
  - run PostgreSQL command line: `psql`
    - Give this user privileges on this database, e.g.:<br>
      `GRANT ALL PRIVILEGES ON DATABASE mydb TO jdoe;`
    - Also allow this user to create new databases (needed for running tests),
      e.g.:<br>
      `ALTER USER jdoe CREATEDB;`
    - Quit: `\q`
  - Exit postgres user login: `exit`

### Clone repository and set up .env

* **Clone the repository**
  * `git clone https://github.com/PersonalGenomesOrg/genevieve`
* **Copy `env.example` to `.env`** (note the leading dot!)
  * Set your `SECRET_KEY` with a random string.
  * Set up email. The easiest for development purposes is probably: `EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"`
  * Set up other environment variables following instructions in env.example.

### Install Python dependencies

* **Using pip and virtualenv, install required packages in a virtualenv**
  * If pip + virtualenv are new to you, check out OpenHatch's [pip and virtualenv](https://openhatch.org/missions/pipvirtualenv) mission (this has instructions and/or links to guides for Debian/Ubuntu, Fedora, and Mac OS X).
  * Make a virtual environment, e.g. `mkvirtualenv genevieve`
  * Install packages in this virtual environment: `pip install -r requirements.txt`
  * Later steps which need to be done in this virtual environment will be marked with **[in virtualenv]**

### Migrate database, start celery, and run the site

* **[in virtualenv] Initialize the database:** `python manage.py migrate`
* **[in virtualenv] Run celery:** In one window, run celery (used for genome processing): `celery -A genevieve_client worker -l info`
* **[in virtualenv] Run the web server:** In another window, run: `python manage.py runserver`

You can now load Genevieve in your web browser by visiting `http://localhost:8000/`
