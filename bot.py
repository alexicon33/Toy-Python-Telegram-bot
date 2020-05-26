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
                   ORDER BY cnt;""",
     'congestion': """SELECT DISTINCT point_from || '-->' || point_to, COUNT(*) AS cnt FROM Moves 
                      WHERE arrival BETWEEN :start AND :finish OR departure BETWEEN :start AND :finish
                      GROUP BY point_from || '-->' || point_to 
                      ORDER BY cnt;"""}


def start(bot, update):
    db = sqlite3.connect('Bot_base.db',
                         detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    cur = db.cursor()
    cur.executescript(open('script.sql', 'r').read())
    db.commit()
    db.close()
    bot.send_message(chat_id=update.message.chat_id,
                     text='\n'.join([
                         "Привет!",
                         "Я бот для работы с транспортной сетью.",
                          "/help - узнать список команд."
                     ]))


# Добавление объекта с указанным id в указанный пункт point.
def insert(bot, update, args):
    if not check(bot, update, args, 2):
        return
    try:
        db = sqlite3.connect('Bot_base.db',
                             detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        cur = db.cursor()
        id, point = args
        cur.execute(q['insert'], (id, point, datetime.datetime.now()))
        db.commit()
        bot.send_message(chat_id=update.message.chat_id,
                         text='Объект {} успешно добавлен в пункт {}.'.format(id, point))
    except sqlite3.Error as err:
        bot.send_message(chat_id=update.message.chat_id,
                         text='Ошибка при работе с базой данных: ' + str(err))


# Удаление объекта с указанным id из базы.
def delete(bot, update, args):
    if not check(bot, update, args, 1):
        return
    db = sqlite3.connect('Bot_base.db',
                         detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    cur = db.cursor()
    id, = args
    cur.execute('SELECT 1 FROM Network WHERE id = ?', (id, ))
    if not len(cur.fetchall()):
        bot.send_message(chat_id=update.message.chat_id,
                         text='Данный объект отсутствует в таблице.')
        return
    cur.execute(q['delete'], (id, ))
    db.commit()
    bot.send_message(chat_id=update.message.chat_id,
                     text='Объект {} успешно удалён.'.format(id))


# Отправление объекта с указанным id из пункта point_from в пункт point_to.
def depart(bot, update, args):
    if not check(bot, update, args, 3):
        return
    db = sqlite3.connect('Bot_base.db',
                         detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    cur = db.cursor()
    id, point_from, point_to = args
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
    if not check(bot, update, args, 1):
        return
    id, = args
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
    if not check(bot, update, args, 1):
        return
    point, = args
    db = sqlite3.connect('Bot_base.db',
                         detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    cur = db.cursor()
    cur.execute(q['count_objects'], (point, ))
    db.commit()
    bot.send_message(chat_id=update.message.chat_id,
                     text='На данный момент в пункте {} объектов: '.format(point) +
                          [str(i) for row in cur for i in row][0] + '.')


# Позволяет узнать, где находится объект с указанным id.
def where(bot, update, args):
    if not check(bot, update, args, 1):
        return
    id, = args
    db = sqlite3.connect('Bot_base.db',
                         detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    cur = db.cursor()
    cur.execute(q['where'], (id, ))
    result_list = cur.fetchall()
    # Возможные варианты - объект может быть в таблице состояния, таблице перемещения или не быть нигде.
    if len(result_list):
        bot.send_message(chat_id=update.message.chat_id,
                         text='Объект {} в пункте '.format(id) +
                              [str(i) for row in result_list for i in row][0] + '.')
        return
    cur.execute(q['where_on_path'], (id, ))
    result_list = cur.fetchall()
    if len(result_list):
        bot.send_message(chat_id=update.message.chat_id,
                         text='Объект {} в пути от '.format(id) +
                              ' до '.join([str(i) for row in result_list for i in row]) + '.')
        return
    bot.send_message(chat_id=update.message.chat_id,
                     text='Объект {} нигде не обнаружен.'.format(id))


# Подсчёт количества объектов на конкретном указанном пути.
def on_the_road(bot, update, args):
    if not check(bot, update, args, 2):
        return
    point_from, point_to = args
    db = sqlite3.connect('Bot_base.db',
                         detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    cur = db.cursor()
    cur.execute(q['on_the_road'], (point_from, point_to))
    bot.send_message(chat_id=update.message.chat_id,
                     text='Сейчас в пути от {} до {} объектов: '.format(point_from, point_to) +
                          [str(i) for row in cur for i in row][0] + '.')


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
    temp = cur.fetchall()
    if not len(temp):
        bot.send_message(chat_id=update.message.chat_id,
                         text='Нет объектов - нет диаграммы...')
        return
    x, y = zip(*temp)
    fig = plt.figure()
    plt.bar(x, y, width=1.2 / len(x), color=(0.01, 0.51, 0.76), alpha=0.75)
    plt.title('Objects distribution')
    plt.grid(True)
    fig.savefig('diagram.png')
    bot.send_photo(chat_id=update.message.chat_id, photo=open('diagram.png', 'rb'))


# Построение диаграммы загруженности путей. Если эта функция вызывается без аргументов,
# строится диаграмма загруженности путей на текущий момент. Если она вызывается с двумя аргументами -
# начальным и конечным временем, строится диаграмма загруженности путей в течение заданного временного промежутка.
def traffic(bot, update, args):
    if len(args) != 0 and len(args) != 2:
        check(bot, update, args, 0)
        return
    db = sqlite3.connect('Bot_base.db',
                         detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    cur = db.cursor()
    if len(args) == 0:
        cur.execute(q['traffic'])
    if len(args) == 2:
        start = [int(i) for i in args[0].split('-')]
        finish = [int(i) for i in args[1].split('-')]
        cur.execute(q['congestion'], {'start': datetime.datetime(*start), 'finish': datetime.datetime(*finish)})
    temp = cur.fetchall()
    if not len(temp):
        bot.send_message(chat_id=update.message.chat_id,
                         text='Все дороги пусты!')
        return
    x, y = zip(*temp)
    fig = plt.figure()
    plt.bar(x, y, width=1.2 / len(x), color=(0.01, 0.51, 0.76), alpha=0.75)
    if len(args) == 0:
        plt.title('Current traffic congestion')
    else:
        plt.title('Traffic congestion during this time')
    plt.grid(True)
    fig.savefig('traffic.png')
    bot.send_photo(chat_id=update.message.chat_id, photo=open('traffic.png', 'rb'))


# Вывод списка допустимых команд.
def commands(bot, update):
    bot.send_message(chat_id=update.message.chat_id,
                     text='\n'.join([
                         "Команды для работы со мной:",
                         "/insert id point - добавить объект c идентификатором id в пункт point",
                         "/delete id - удалить объект с идентификатором id",
                         "/depart id from to - отправить объект с данным id из пункта from в пункт to",
                         "/arrive id - сообщение о прибытии объекта с данным id в пункт назначения",
                         "/count_objects point - количество объектов в пункте point на данный момент",
                         "/where id - где находится объект с данным id в настоящее время",
                         "/on_the_road from to - сколько объектов сейчас находятся на пути из пункта from в пункт to",
                         "/od - посмотреть диаграмму, показывающую, сколько объектов в каждом пункте",
                         "/traffic - посмотреть диаграмму, отражающую загруженность путей на данный момент",
                         "/traffic start finish посмотреть диаграмму, отражающую загруженность путей "
                         "в течение времени от start до finish включительно.",
                         "/stat - вывести имеющиеся данные."
                     ]))


# Проверка на то, что число аргументов равно number.
def check(bot, update, args, number):
    if len(args) != number:
        bot.send_message(chat_id=update.message.chat_id,
                         text='\n'.join([
                             "Ошибка: неправильное число аргументов.",
                             "Ожидалось: {}".format(number),
                             "Получено: {}".format(len(args))]))
        return False
    return True


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
    dp.add_handler(CommandHandler('traffic', traffic, pass_args=True))
    dp.add_handler(CommandHandler('help', commands))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
