import schedule
import time
from tasks import  task
import pytz


def job():
    print("I'm working...")



schedule.every().day.at("10:57", 'America/Sao_Paulo').do(job)


while 1:

    n = schedule.idle_seconds()
    print(n)

    if n == None:
        print("No more jobs")
        break
    elif n > 0 :
        print(f"Sleeping {n} seconds before next job")
        time.sleep(n)
        

    schedule.run_pending()

    