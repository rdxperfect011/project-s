from sqlalchemy import inspect
from app import db, app

with app.app_context():
    db.create_all()
    print("✅ Database created successfully!")

    # Display all table names to confirm creation (SQLAlchemy 2.x compatible)
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    if tables:
        print("📋 Tables in the database:", tables)
    else:
        print("⚠️ No tables found. Check your models or database URI configuration.")