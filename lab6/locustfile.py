from locust import HttpUser, task, between

class OpenBMCUser(HttpUser):
    wait_time = between(1, 3)
    host = "https://localhost:5000"

    def on_start(self):
        self.client.auth = ("root", "0penBmc")
        self.client.verify = False

    @task(2)
    def get_system_info(self):
        self.client.get("/redfish/v1/Systems/system", name="OpenBMC: System Info")

    @task(1)
    def get_power_state(self):
        response = self.client.get("/redfish/v1/Systems/system", name="OpenBMC: PowerState")


class PublicAPIUser(HttpUser):
    wait_time = between(1, 2)
    host = ""

    @task(2)
    def get_posts(self):
        self.client.get("https://jsonplaceholder.typicode.com/posts", name="JSONPlaceholder: Posts")

    @task(1)
    def get_weather(self):
        self.client.get("https://wttr.in/Novosibirsk?format=j1", name="wttr.in: Weather")