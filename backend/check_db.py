import pymysql
conn=pymysql.connect(host='localhost', user='root', password='admin')
cursor=conn.cursor()
cursor.execute('SHOW DATABASES LIKE "study_assistant"')
print('DB exists:', bool(cursor.fetchone()))
