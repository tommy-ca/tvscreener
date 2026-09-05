from sqlalchemy.engine.url import make_url

url = make_url("sqlite://///tmp/dir?key=value/catalog.db")
print("Database:", url.database)
print("Query:", url.query)
