# %%
from zef import *
from zef.ops import *
from zef.gql import *
from time import sleep
import os

worduel_tag = os.getenv('TAG', "worduel/main3")
if __name__ == "__main__":
    g = Graph(worduel_tag)
    make_primary(g, True)  # To be able to perform mutations locally without needing to send merge requests
    Effect({
        "type": FX.GraphQL.StartServer,
        "schema_root": gql_schema(g),
        "port": 5010,
        "bind_address": "0.0.0.0",
    }) | run
    
    while True: sleep(1)
# %%
