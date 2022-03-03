# %%
from zef import *
from zef.ops import *
from zef.gql import *
from time import sleep
import os

worduel_tag = os.getenv('TAG', "worduel-api")
if __name__ == "__main__":
    g = Graph(worduel_tag)
    make_primary(g, True)
    Effect({
        "type": FX.GraphQL.StartPlayground,
        "schema_root": gql_schema(g),
        "port": 5010,
    }) | run
    while True: sleep(1)
# %%
