#! /usr/bin/env python3
import drillmaster

class Database(drillmaster.Service):
    name = "appdb"
    image = "postgres:10.6"
    env = {"POSTGRES_PASSWORD": "dbpwd",
           "POSTGRES_USER": "dbuser",
           "POSTGRES_DB": "appdb",
           "PGPORT": 5433 }
    ports = {5433: 5433}

class Application(drillmaster.Service):
    name = "python-todo"
    image = "afroisalreadyin/python-todo:0.0.1"
    env = {"DB_URI": "postgresql://dbuser:dbpwd@appdb:5433/appdb"}
    dependencies = ["appdb"]

if __name__ == "__main__":
    drillmaster.cli()
