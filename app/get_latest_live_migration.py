import pymysql


def get_last_live_migration(db_host, db_user, db_password, db_name="nova"):
    conn = pymysql.connect(
        host=db_host,
        user=db_user,
        password=db_password,
        database=db_name,
        cursorclass=pymysql.cursors.DictCursor
    )

    try:
        with conn.cursor() as cursor:
            query = """
                SELECT instance_uuid, source_compute, dest_compute, created_at
                FROM migrations
                WHERE migration_type='live-migration'
                ORDER BY created_at DESC
                LIMIT 1
            """
            cursor.execute(query)
            result = cursor.fetchone()
            return result
    finally:
        conn.close()


if __name__ == "__main__":
    result = get_last_live_migration(
        db_host="10.10.10.136",
        db_user="nova",
        db_password="yAGUGMGchBxFx0zQap72RCsaRABO5Fb6kOFLKdLn"
    )

    if result:
        print("Last live migration:")
        print(f"Instance UUID : {result['instance_uuid']}")
        print(f"Source Compute    : {result['source_compute']}")
        print(f"Destination Compute : {result['dest_compute']}")
        print(f"Created At    : {result['created_at']}")
        #print(f"Updated At   : {result['updated_at']}")
    else:
        print("No live migration found")