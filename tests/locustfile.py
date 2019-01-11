from locust import HttpLocust, TaskSet


def index(l):
    l.client.get("/")


def taxo(l):
    l.client.get("/taxonomy/objets/1")


def classes(l):
    l.client.get("/taxonomy_classes/1")


class UserBehavior(TaskSet):
    tasks = {
        index: 1,
        taxo: 1,
        classes: 1,
    }


class WebsiteUser(HttpLocust):
    task_set = UserBehavior
    min_wait = 700
    max_wait = 1300
