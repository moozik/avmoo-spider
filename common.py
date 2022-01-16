def get_db_file():
    return 'avmoo.db'

def get_country():
    return 'cn'

def show_column_name(data, description) -> list:
    result = []
    for row in data:
        row_dict = {}
        for i in range(len(description)):
            row_dict[description[i][0]] = row[i]
        result.append(row_dict)
    return result

def fetchall(cur, sql) -> list:
    cur.execute(sql)
    ret = cur.fetchall()
    return show_column_name(ret, cur.description)