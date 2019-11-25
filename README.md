# vvWeb

Django web app to run and display results from VariantValidator

## Installation

Download the source files through git

```bash
git clone https://github.com/openvar/vvweb
cd vvweb
```

To install the python packages you should first create a python 3.6 virtual environment.

```bash
# if you have conda installed
conda env create -f environment.yml
conda activate vvweb

# otherwise
module load python/gcc/3.6.4  # only if on SPECTRE
python -m venv env
source env/bin/activate
pip install -r requirements.txt
```

This will install the latest VariantValidator (master branch of GitHub repo). You'll need to make sure VariantValidator is
working correctly before proceeding any further. See the [VV git repo](https://github.com/openvar/variantValidator) for help.


## Web Setup

Once everything is installed and you've got a complete virtual environment, you then need to setup the django app.

### Postgres Database

VVweb uses postgres, you therefore need to setup and create a user account and database specific for this task.
Follow the settings (changing the inputs accordingly) below:

```postgresql
CREATE DATABASE myproject;
CREATE USER myprojectuser WITH PASSWORD 'password';
ALTER ROLE myprojectuser SET client_encoding TO 'utf8';
ALTER ROLE myprojectuser SET default_transaction_isolation TO 'read committed';
ALTER ROLE myprojectuser SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE myproject TO myprojectuser;
```

### Settings

Create a `local_settings.py` file within `VVweb/`. Inside should be all private settings, including a hash secret key. It should look something like:

```python
from .settings import DATABASES

# Ensure you don't use the key below - it should be something different!
SECRET_KEY = '+htjqfu=nn$+(vcs8sdx1=^2lprn8pj(s1zs4z4jv$*l%pxs68'

DATABASES['default']['NAME'] = 'myproject'
DATABASES['default']['USER'] = 'myprojectuser'
DATABASES['default']['PASSWORD'] = 'password'

# List of Admins, with their email address that will get emailed if an error is reported.
ADMINS = [
    ('Teri', 'trf5@le.ac.uk'),
]

RECAPTCHA_PUBLIC_KEY = 'key goes here'
RECAPTCHA_PRIVATE_KEY = 'key goes here'

```

To then create the database tables, make a migration (checks what models need creating) and then migrate it into the database.

```bash
python manage.py makemigrations
python manage.py migrate
```

Once this is done, you need to create an admin user account to access the web admin site. Make sure you don't lose track
of this username and password.

```bash
python manage.py createsuperuser
```

Then, you should be able to launch the development server

```bash
python manage.py runserver
```

### APIs and social accounts

For the user authentication and re-captcha to work, you need to set up the app with the appropriate sites.

For re-captcha, go to their site https://www.google.com/recaptcha/intro/v3.html and register the app. Create a 'v2 tickbox' recaptcha. This will 
create a public and private key, both of which need to go in the `local_settings.py` file.

The social account logins for GitHub, Google and ORCID are setup using django-allauth. Their [documentation](https://django-allauth.readthedocs.io/en/latest/providers.html)
describes how to setup each one. You'll need to go to the admin site (http://localhost:8000/admin/) to save the public and private keys. 

## Celery and RabbitMQ

To run the batch processes, you'll need to install and setup [RabbitMQ](https://www.rabbitmq.com/download.html) and [Celery](http://docs.celeryproject.org/en/latest/index.html).

To run asynchronous tasks you need celery to talk to the Django app, via a broker (in our case RabbitMQ).
Once RabbitMQ is running it should be connected to port 5672. This can be done by installing RabbitMQ from an RPM, from source or via a docker image.

```bash
# Docker 
docker run -d --hostname my-rabbit --name some-rabbit -p 5672:5672 rabbitmq
```

For the LAMPs, Liam can install RabbitMQ and ensure that it starts on reboot.

Once the rabbit service is running, start Celery using the provided script `run_celery.sh`. 
This will start both celery and celery-beat which will listen for tasks and run them asynchronously.
This script will need to be set to run on reboot along with all other services.

To set up the celery-beat tasks (that is the daily jobs), go into the admin interface and create a series of cron times (e.g. to run at 1AM each day).
You can then select a celery task, and a cron time and these jobs will continue to run while the service is operating.
There are three tasks that need setting up this way, `delete_old_jobs`, `email_old_users` and `delete_old_users`. 

### Deployment

Once all the settings are set and celery is up and running, get apache to serve both static and app files.

See Django's own documentation on serving the files with apache.
 
Make sure that the DEBUG setting
is set to False! Also, change allowed_hosts setting to include the new domain name - that also needs setting in the admin interface.

## Submitting changes

To make a change to vvWeb, first checkout a new branch within git.

```bash
# pull in latest changes
git pull
# -b creates a new branch
git checkout -b new_branch_name
```

Your branch name should be specific to the task you're working on. If you want to work on two or more tasks, each should go in their own branch.

Once you've made a change, commit it into git by selecting the files you want to commit, and then making the commit with a message.
Commits should be atomic, i.e. "of or forming a single irreducible unit or component in a larger system". So as small as possible, but containing all changes
related to that one thing. For example, if we wanted to change the name of the validator we'd make one commit that contains that change in all the relevant files. 
If we spotted a typo at the same time, that would go in a separate commit as it's not part of the validator name change.
This means that if we decide to undo the validator name change, we wouldn't also undo the typo fix.

```bash
git add file1 file4
git add --patch file2  # this will allow you to add only part of the file
git commit -m "Message describing my change"
```

Once you've made your commits, push them to the remote version on GitHub (called origin)

```bash
git push -u origin new_branch_name
```

Once you've done all the work for that branch/task, and it's been pushed to GitHub, make a Pull Request
online to suggest merging your new branch into master. Assign me as a reviewer so I get emailed about your PR. Once I've merged the change,
I'll delete the new branch.

To then start working on a new task/branch, checkout master, ensure it's up-to-date and then make a new branch.
When you branch it contains all the changes from the branch you're currently on, which is why you want to make sure
that you're starting from the right place.

```bash
git checkout master
git pull
git checkout -b another_new_branch
```

If you're ever unsure about what changes are in your current working directory, or
which branch you're on run `git status`. In fact I run that before, during and after every
add/commit to make sure I've got the right files and am in the right place before committing anything.
