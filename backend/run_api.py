# %%
from zef import *
from zef.ops import *
from zef.gql import *
from time import sleep
import os

worduel_tag = os.getenv('TAG', "worduel/main2")
if __name__ == "__main__":
    g = Graph(worduel_tag)
    # make_primary(g, True)
    Effect({
        "type": FX.GraphQL.StartServer,
        "schema_root": gql_schema(g),
        "port": 5010,
        "open_browser": False,
        "bind_address": "0.0.0.0",
    }) | run
    while True:
        sleep(1)
# %%
