from telegram.ext import Updater, CommandHandler
import sqlite3
import datetime
import matplotlib.pyplot as plt


# Словарь нужных для работы бота sql-запросов.
q = {'insert': """INSERT INTO Network VALUES(?, ?, ?);""",
     'delete': """DELETE FROM Network WHERE id = ?;""",
     'depart': """INSERT INTO Moves (id, point_from, point_to, departure) VALUES(?, ?, ?, ?);""",
     'arrive': """UPDATE Moves SET arrival = ? WHERE id = ? AND arrival is NULL;""",
     'stat_network': """SELECT * FROM Network;""",
     'stat_moves': """SELECT * FROM Moves;""",
     'count_objects': """SELECT COUNT(*) FROM Network WHERE point = ?;""",
     'where': """SELECT point FROM Network WHERE id = ?;""",
     'on_the_road': """SELECT COUNT(*) FROM Moves WHERE arrival IS NULL AND point_from = ? AND point_to = ?;""",
     'diagram_points': """SELECT point, COUNT(*) AS cnt FROM Network GROUP BY point ORDER BY cnt;""",
     'where_on_path': """SELECT point_from, point_to FROM Moves WHERE id = ? AND arrival IS NULL;""",
     'traffic': """SELECT DISTINCT point_from || '-->' || point_to, COUNT(*) AS cnt FROM Moves
                           WHERE arrival IS NULL
                           GROUP BY point_from || '-->' || point_to
                           ORDER BY cnt;"""}


def start(bot, update):
    db = sqlite3.connect('Bot_base.db',
                         detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    cur = db.cursor()
    cur.executescript(open('script.sql', 'r').read())
    db.commit()
    db.close()
    bot.send_message(chat_id=update.message.chat_id, text="Привет!\nЯ бот для работы с транспортной сетью.\n" +
                     "/help - узнать список команд.")


# Добавление объекта с указанным id в указанный пункт point.
def insert(bot, update, args):
    db = sqlite3.connect('Bot_base.db',
                         detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    cur = db.cursor()
    point = args[1]
    id = args[0]
    cur.execute(q['insert'], (id, point, datetime.datetime.now()))
    db.commit()
    bot.send_message(chat_id=update.message.chat_id,
                     text='Объект {} успешно добавлен в пункт {}.'.format(id, point))


# Удаление объекта с указанным id из базы.
def delete(bot, update, args):
    db = sqlite3.connect('Bot_base.db',
                         detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    cur = db.cursor()
    id = args[0]
    cur.execute(q['delete'], (id, ))
    db.commit()
    db.close()
    bot.send_message(chat_id=update.message.chat_id,
                     text='Объект {} успешно удалён.'.format(id))


# Отправление объекта с указанным id из пункта point_from в пункт point_to.
def depart(bot, update, args):
    db = sqlite3.connect('Bot_base.db',
                         detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    cur = db.cursor()
    id = args[0]
    point_from = args[1]
    point_to = args[2]
    cur.execute('SELECT 1 FROM Network WHERE id = ? AND point = ?', (id, point_from))
    if not len(cur.fetchall()):
        bot.send_message(chat_id=update.message.chat_id,
                         text='Этот объект не находится в данном городе.'.format(id))
        return
    # Объект должен добавиться в таблицу перемещений и уйти из таблицы состояния.
    cur.execute(q['delete'], (id, ))
    cur.execute(q['depart'], (id, point_from, point_to, datetime.datetime.now()))
    db.commit()
    bot.send_message(chat_id=update.message.chat_id,
                     text='Объект {} успешно отправлен в пункт {}!'.format(id, point_to))


# Прибытие объекта с указанным id в пункт назначения.
def arrive(bot, update, args):
    id = args[0]
    db = sqlite3.connect('Bot_base.db',
                         detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    cur = db.cursor()
    cur.execute('SELECT 1 FROM Moves WHERE id = ? AND arrival IS NULL', (id,))
    if not len(cur.fetchall()):
        bot.send_message(chat_id=update.message.chat_id,
                         text='Этот объект не находится в пути.'.format(id))
        return
    # Производим обратные действия - добавляем объект в таблицу состояния и удаляем из таблицы перемещения.
    now = datetime.datetime.now()
    cur.execute(q['arrive'], (now, id))
    cur.execute('SELECT point_to FROM Moves WHERE id = ? AND arrival = ?', (id, now))
    city_to = ''
    for row in cur:
        for i in row:
            city_to = i
    cur.execute(q['insert'], (id, city_to, datetime.datetime.now()))
    db.commit()
    bot.send_message(chat_id=update.message.chat_id,
                     text='Объект {} успешно прибыл в пункт назначения.'.format(id))


# Подсчёт количетсва объектов в некотором указанном пункте.
def count_objects(bot, update, args):
    point = args[0]
    db = sqlite3.connect('Bot_base.db',
                         detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    cur = db.cursor()
    cur.execute(q['count_objects'], (point, ))
    db.commit()
    bot.send_message(chat_id=update.message.chat_id,
                     text='На данный момент в пункте {} объектов: '.format(point) +
                          '\n'.join(' '.join(str(i) for i in row) for row in cur) + '.')


# Позволяет узнать, где находится объект с указанным id.
def where(bot, update, args):
    id = args[0]
    db = sqlite3.connect('Bot_base.db',
                         detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    cur = db.cursor()
    cur.execute(q['where'], (id, ))
    result_list = cur.fetchall()
    # Возможные варианты - объект может быть в таблице состояния, таблице перемещения или не быть нигде.
    if len(result_list):
        bot.send_message(chat_id=update.message.chat_id,
                         text='Объект {} в пункте '.format(id) +
                              '\n'.join(' '.join(str(i) for i in row) for row in result_list) + '.')
        return
    cur.execute(q['where_on_path'], (id, ))
    result_list = cur.fetchall()
    if len(result_list):
        bot.send_message(chat_id=update.message.chat_id,
                         text='Объект {} в пути от '.format(id) +
                              ''.join(' до '.join(str(i) for i in row) for row in result_list) + '.')
        return
    bot.send_message(chat_id=update.message.chat_id,
                     text='Объект {} нигде не обнаружен.'.format(id))


# Подсчёт количества объектов на конкретном указанном пути.
def on_the_road(bot, update, args):
    point_from = args[0]
    point_to = args[1]
    db = sqlite3.connect('Bot_base.db',
                         detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    cur = db.cursor()
    cur.execute(q['on_the_road'], (point_from, point_to))
    bot.send_message(chat_id=update.message.chat_id,
                     text='Сейчас в пути от {} до {} объектов: '.format(point_from, point_to) +
                          ''.join(''.join(str(i) for i in row) for row in cur) + '.')


# Полный вывод обеих табличек.
def stat(bot, update):
    db = sqlite3.connect('Bot_base.db',
                         detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    cur = db.cursor()
    cur.execute(q['stat_network'])
    bot.send_message(chat_id=update.message.chat_id,
                     text="Here is Network table:\n" + '\n'.join(' '.join(str(i) for i in row) for row in cur))
    cur.execute(q['stat_moves'])
    bot.send_message(chat_id=update.message.chat_id,
                     text="Here is Moves table:\n" + '\n'.join(' '.join(str(i) for i in row) for row in cur))


# Построение диаграммы распределения объектов по различным пунктам.
# Пункты сортируются по количеству объектов в них.
def objects_distribution(bot, update):
    db = sqlite3.connect('Bot_base.db',
                         detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    cur = db.cursor()
    cur.execute(q['diagram_points'])
    x = []
    y = []
    for row in cur:
        x += [row[0]]
        y += [row[1]]
    if not len(x):
        bot.send_message(chat_id=update.message.chat_id,
                         text='Нет объектов - нет диаграммы...')
        return
    fig = plt.figure()
    plt.bar(x, y, width=1.2 / len(x), color=(0.01, 0.51, 0.76), alpha=0.75)
    plt.title('Objects distribution')
    plt.grid(True)
    fig.savefig('diagram.png')
    bot.send_photo(chat_id=update.message.chat_id, photo=open('diagram.png', 'rb'))


# Построение диаграммы загруженности путей на текущий момент.
def traffic(bot, update):
    db = sqlite3.connect('Bot_base.db',
                         detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    cur = db.cursor()
    cur.execute(q['traffic'])
    x = []
    y = []
    for row in cur:
        x += [row[0]]
        y += [row[1]]
    if not len(x):
        bot.send_message(chat_id=update.message.chat_id,
                         text='Все дороги пусты!')
        return
    fig = plt.figure()
    plt.bar(x, y, width=1.2 / len(x), color=(0.01, 0.51, 0.76), alpha=0.75)
    plt.title('Traffic congestion')
    plt.grid(True)
    fig.savefig('traffic.png')
    bot.send_photo(chat_id=update.message.chat_id, photo=open('traffic.png', 'rb'))


# Вывод списка допустимых команд.
def commands(bot, update):
    bot.send_message(chat_id=update.message.chat_id,
                     text="Команды для работы со мной\n" +
                          "/insert id point - добавить объект c идентификатором id в пункт point\n" +
                          "/delete id - удалить объект с идентификатором id\n" +
                          "/depart id from to - отправить объект с данным id из пункта from в пункт to\n" +
                          "/arrive id - сообщение о прибытии объекта с данным id в пункт назначения\n" +
                          "/count_objects point - количество объектов в пункте point на данный момент\n" +
                          "/where id - где находится объект с данным id в настоящее время\n" +
                          "/on_the_road point_from point_to - сколько объектов сейчас находятся на пути " +
                                                              "из point_from в point_to\n" +
                          "/od - посмотреть диаграмму, показывающую, сколько объектов в каждом пункте\n" +
                          "/traffic - посмотреть диаграмму, отражающую загруженность путей на данный момент\n" +
                          "/stat - вывести имеющиеся данные.")


def main():
    updater = Updater(token=open('input.txt', 'r').read())
    dp = updater.dispatcher
    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(CommandHandler('insert', insert, pass_args=True))
    dp.add_handler(CommandHandler('delete', delete, pass_args=True))
    dp.add_handler(CommandHandler('depart', depart, pass_args=True))
    dp.add_handler(CommandHandler('arrive', arrive, pass_args=True))
    dp.add_handler(CommandHandler('count_objects', count_objects, pass_args=True))
    dp.add_handler(CommandHandler('where', where, pass_args=True))
    dp.add_handler(CommandHandler('on_the_road', on_the_road, pass_args=True))
    dp.add_handler(CommandHandler('stat', stat))
    dp.add_handler(CommandHandler('od', objects_distribution))
    dp.add_handler(CommandHandler('traffic', traffic))
    dp.add_handler(CommandHandler('help', commands))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
