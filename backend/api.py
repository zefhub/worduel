# TODO add is_out somehow from the schemas directly. Pass with connecting function
# TODO create Delegates?
# TODO zef functions to take more than default args?
#%%
from zef import * 
from zef.ops import * 
from zef.gql import *
from zef.gql.generate_gql_api import generate_graph_from_file, make_api
from zef.gql.resolvers_utils import *
from schema import schema_gql


g = Graph()
generate_graph_from_file(schema_gql, g)


url = "https://raw.githubusercontent.com/charlesreid1/five-letter-words/master/sgb-words.txt"
words = url | make_request | run | get['response_text']   | collect
(ET.WordList, RT.FiveLetters, words) | g | run

# ----------------UTILS--------------------------------

# ----------------UTILS--------------------------------

"""
userA  = create_user("A", g)
duel   = create_duel(userA, g)
game   = create_game("guess", duel, userA, g)['id']
userB  = create_user("B", g)
accept_duel(duel, userB, g)

submit_guess(game, "CRANE", g)
submit_guess(game, "GUEST", g)
submit_guess(game, "Black", g)
submit_guess(game, "flank", g)

submit_guess(game, "guess", g)   
submit_guess(game, "stake", g)    # already completed

# submit_guess(game, "small", g) # FAILED
# submit_guess(game, "guess", g)   # SOLVED

# submit_guess(game, "MIST", g)   # not 5 letters
# submit_guess(game, "CRANE", g)  # used before
# submit_guess(game, "ZEYAD", g)  # not in wordlist

# yo(get_game(game, g))
"""
############--Mutations--###############
# createUser(name: String): ID
@func(g)
def create_user(name: str, g: VT.Graph, **defaults) -> str:
    r = GraphDelta([
        (ET.Player['p1'], RT.Name, name)
    ]) | g | run

    return str(r['p1'] | to_ezefref | uid | collect)


# createDuel(creatorId: ID): ID 
@func(g)
def create_duel(creator_id: str, g: VT.Graph, **defaults) -> str:
    r = GraphDelta([
        (ET.Duel['d1'], RT.Participant, g[creator_id]),
    ]) | g | run

    return str(r['d1'] | to_ezefref | uid | collect)



# createGame(solution: String, duelId: ID, creatorId: ID): ID 
@func(g)
def create_game(solution: str, duel_id: str, creator_id: str,  g: VT.Graph, **defaults) -> str:
    def make_return(msg: str = "", game_id: str = "", success: bool  = False):
        return {"message": msg, "id": game_id, "success": success}
    solution = to_upper(solution)
    # Creating a game for a duel that doesn't exist
    if duel_id not in g: return make_return("Given duel_id doesn't exist in the Graph")
    # Creating a game for a player that doesn't exist
    if creator_id not in g: return make_return("Given creator_id doesn't exist in the Graph")

    duel_games = now(g[duel_id]) >> L[RT.Game] 
    if length(duel_games) == 0:
        r = GraphDelta([
            (ET.Game['g1'], RT.Solution,    solution),
            (Z['g1'],       RT.Creator,     g[creator_id]),
            (Z['g1'],       RT.Completed,   False),
            (g[duel_id],    RT.Game,        Z['g1']),
        ]) | g | run

    else:
        last_game = duel_games | last | collect

        last_completed = last_game >> RT.Completed | value | collect
        if not last_completed: return make_return("Last game in this duel isn't completed yet.")

        # These must exist if we are creating a new game
        if length(last_game >> L[RT.Creator]) != 1: return make_return("A creator doesn't exist for last game")
        if length(last_game >> L[RT.Player])  != 1: return make_return("A player doesn't exist for last game")

        player  = last_game >> RT.Player  | collect
        creator = last_game >> RT.Creator | collect

        # The creator must be last game's player
        if creator_id != str(uid(player | to_ezefref)): return make_return("Last creator can't create this game.")

        r = GraphDelta([
            (ET.Game['g1'], RT.Solution,    solution),
            (Z['g1'],       RT.Creator,     player),
            (Z['g1'],       RT.Player,      creator),
            (Z['g1'],       RT.Completed,   False),
            (g[duel_id],    RT.Game,        Z['g1']),
        ]) | g | run

    
    return make_return("", str(r['g1'] | to_ezefref | uid | collect), True)
    

# acceptDuel(duelId: ID, playerId: ID): Boolean
@func(g)
def accept_duel( duel_id: str, player_id: str, g: VT.Graph, **defaults) -> str:
    connected_games = now(g[duel_id]) >> L[RT.Game] 
    if length(connected_games) == 1:       # There must be only one game attached!
        first_game = connected_games | first | collect

        if length(first_game >> L[RT.Player]) == 0:    # The player wasn't attached yet
            GraphDelta([
                (g[duel_id], RT.Participant, g[player_id]),
                (first_game, RT.Player, g[player_id])
            ]) | g | run

            return str(first_game | to_ezefref | uid | collect)

    return ""

# submitGuess(gameId: ID, guess: String): SubmitGuessReturnType
@func(g)
def submit_guess(game_id, guess, g: VT.Graph, **defaults):
    def make_return(is_eligible: bool  = True, solved: bool = False, failed: bool = False, guess_result: str = "", message: str = ""):
        return {"isEligibleGuess": is_eligible, "solved": solved, "failed": failed, "guessResult": guess_result, "message": message}
    
    def make_guess(guess, to_be_guessed):
        def dispatch_letter(arg):
            i, c = arg
            nonlocal to_be_guessed
            if c == to_be_guessed[i]:         
                to_be_guessed = replace_at(i, c.lower(), to_be_guessed)
                return c
            elif c in to_be_guessed:         
                to_be_guessed = replace_at(to_be_guessed.rindex(c), c.lower(), to_be_guessed)
                return f"[{c}]"
            else:                             
                # if Not[contains[c.lower()]](to_be_guessed): discard_letters.add(c)
                return "_"
        
        return (guess                       
                | enumerate                 
                | map[dispatch_letter]      
                | collect 
            )#, discard_letters

    if game_id not in g: return None
    MAX_GUESSES = 6
    game = now(g[game_id])
    guess = to_upper(guess)

    # Don't continue if this game is already completed
    completed = game >> RT.Completed | collect
    if value(completed):
        return make_return(failed = True, message = "This game is already completed.")

    # Early exist if we made correct guess
    solution  = game >> RT.Solution | value | collect
    if guess == solution: 
        GraphDelta([
                    (game, RT.Guess, guess),
                    (completed <= True),
        ]) | g | run
        return make_return(guess_result = make_guess(guess, solution), solved = True)

    wordlist_rt = {5: RT.FiveLetters}[length(solution)]
    wordlist = g | all[wordlist_rt] | first | target | now | value | split['\n'] | map[to_upper] | collect
    previous_guesses = game >> L[RT.Guess] | value | collect
    is_eligible_guess = And[length | equals[length(solution)]][contained_in[wordlist + [solution]]][Not[contained_in[previous_guesses]]]

    if is_eligible_guess(guess):
        guess_result = make_guess(guess, solution)
        # If this is the last guess
        if len(previous_guesses) == MAX_GUESSES - 1:
            GraphDelta([
                    (game, RT.Guess, guess),
                    (completed <= True),
            ]) | g | run
            return make_return(guess_result = guess_result, failed = True)
        else:
            GraphDelta([
                    (game, RT.Guess, guess),
            ]) | g | run
            return make_return(guess_result = guess_result)
    else:
        #TODO more specific messages based on elgibility?
        return make_return(is_eligible = False)


#############--Querys--###############
# getUser(usedId: ID): User
@func(g)
def get_user(user_id: str, g: VT.Graph, **defaults):
    return now(g[user_id])


# getGame(gameId: ID): Game
@func(g)
def get_game(game_id, g: VT.Graph, **defaults):
    return now(g[game_id])


#############--User--###############
@func(g)
def get_user_name(z: VT.ZefRef, **defaults):
    return z >> RT.Name | value | collect

@func(g)
def get_user_duels(z: VT.ZefRef, **defaults):
    return z << L[RT.Participant] | collect


# #############--Duel--###############
@func(g)
def get_duel_players(z: VT.ZefRef, **defaults):
    return z >> L[RT.Participant] | collect

@func(g)
def get_duel_games(z: VT.ZefRef, **defaults):
    return z >> L[RT.Game] | collect


# #############--Game--###############
@func(g)
def get_game_creator(z: VT.ZefRef, **defaults):
    return z >> O[RT.Creator] | collect

@func(g)
def get_game_player(z: VT.ZefRef, **defaults):
    return z >> O[RT.Player] | collect

@func(g)
def get_game_solution(z: VT.ZefRef, **defaults):
    return z >> O[RT.Solution] | value | collect

@func(g)
def get_game_guesses(z: VT.ZefRef, **defaults):
    return z >> L[RT.Guess] | value | collect

@func(g)
def get_game_duel(z: VT.ZefRef, **defaults):
    return z << O[RT.Game] | collect

@func(g)
def get_game_completed(z: VT.ZefRef, **defaults):
    return z >> O[RT.Completed] | maybe_value | collect

#%%
schema = gql_schema(g)
types  = gql_types_dict(schema)

# DefaultResolversList
default_list = ["CreateGameReturnType", "SubmitGuessReturnType"] | to_json | collect
(schema, RT.DefaultResolversList, default_list) | g | run


# CustomerSpecificResolvers
specific_resolvers = (
"""def customer_specific_resolvers(ot, ft, bt, rt, fn):
    from zef.ops import  now, value, collect
    from zef import RT
    if fn == "id" and now(ft) >> RT.Name | value | collect == "GQL_ID":
       return ("return str(z | to_ezefref | uid | collect)", ["z", "ctx"])
    return ("return None #This means that no resolver is defined!", ["z", "ctx"])
""") | collect
(schema, RT.CustomerSpecificResolvers, specific_resolvers) | g | run


# Mutations Handlers
mutations_dict  = {
    "acceptDuel":   accept_duel,
    "createUser":   create_user,
    "createDuel":   create_duel,
    "createGame":   create_game,
    "submitGuess":  submit_guess,
}
connect_zef_function_resolvers(types['GQL_Mutation'], mutations_dict)    



# Query Handlers
query_dict  = {
    "getUser":   get_user,
    "getGame":   get_game,
}
connect_zef_function_resolvers(types['GQL_Query'], query_dict)    


# User Handlers
# TODO Turn to connect_direct_resolvers_to_delegates
user_dict  = {
    "name":   get_user_name,
    "duels":  get_user_duels,
}
connect_zef_function_resolvers(types['GQL_User'], user_dict)   


# Duel Handlers
# TODO Turn to connect_direct_resolvers_to_delegates
# duel_dict  = {
#     "players":   "Participant",
#     "game":      "Game",
# }
# connect_direct_resolvers_to_delegates(g, types['GQL_Duel'], "Duel", duel_dict)

duel_dict  = {
    "players":   get_duel_players,
    "games":     get_duel_games,
}
connect_zef_function_resolvers(types['GQL_Duel'], duel_dict)   


# Game Handlers
# TODO Turn to connect_direct_resolvers_to_delegates
game_dict  = {
    "player":       get_game_player,
    "creator":      get_game_creator,
    "solution":     get_game_solution,
    "duel":         get_game_duel,
    "guesses":      get_game_guesses,
    "completed":    get_game_completed,
}
connect_zef_function_resolvers(types['GQL_Game'], game_dict)   

# import os
# schema_destination = f"{os.getcwd()}/generated_schema.py"
# resolvers_destination = f"{os.getcwd()}/"
# schema = make_api(now(schema), schema_destination, resolvers_destination)


Effect({
        "type": FX.GraphQL.StartPlayground,
        "schema_root": gql_schema(g),
        "port": 5010,
}) | run