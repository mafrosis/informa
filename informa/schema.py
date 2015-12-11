from . import db


class ObjectStore(db.Model):
    plugin_name = db.Column(db.String(100), primary_key=True)
    data = db.Column(db.Text)

    def __init__(self, plugin_name, data):
        self.plugin_name = plugin_name
        self.data = data
