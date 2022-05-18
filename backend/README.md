# Quick overview of Worduel backend

## Blogs to Reference

[Part 1](https://zef.zefhub.io/blog/wordle-using-zefops) Explains the logic behind Wordle, how ZefOps are used.

[Part 2](https://zef.zefhub.io/blog/wordle-solver-one-line) Deeper overview of using ZefOps to a Wordle solver/assistant.


[Part 3](https://zef.zefhub.io/blog/worduel-gql-backend) Explains different resolver types, ZefGQL, ZefFX, and deploying on ZefHub.

## Files Overview

    schema.py 

This files contains one string variable which holds the GraphQL schema.

    make_api.py 

This file adds the GraphQL schema to an empty graph. It also contains all the logic for the resolvers and connects them to the delegates. 

    run_api.py 

As the name suggests, this file runs the api using the FX system.


## Step to build and run

Before running any of the files be sure to set the environment variable `TAG` to the name you want to give to your graph.

1. Run the make_api file, then close that python session.
2. Run the run_api file.

You can add the option `'open_browser': True` to the StartServer effect for the playground to open automatically.
However if it doesn't open, you can access at http://localhost:5010/gql

Be sure to set the port.