import sqlite3


def create_database():

    connection = sqlite3.connect("civiclens.db")

    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS complaints (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            complaint_id TEXT UNIQUE NOT NULL,

            location TEXT NOT NULL,

            description TEXT,

            issue TEXT,

            priority TEXT,

            department TEXT,

            reason TEXT,

            image_filename TEXT,

            status TEXT DEFAULT 'Pending'

        )
    """)

    connection.commit()

    connection.close()

    print("CivicLens database created successfully!")


if __name__ == "__main__":
    create_database()