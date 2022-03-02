#%%
from zef import * 
from zef.ops import * 
from zef.gql import *
from time import sleep

wordle_tag = "wordle-api-0"

if __name__ == "__main__":
    g = Graph(wordle_tag)
    make_primary(g, True)
    Effect({
            "type": FX.GraphQL.StartPlayground,
            "schema_root": gql_schema(g),
            "port": 5010,
    }) | run
    while True: sleep(1)
# %%
