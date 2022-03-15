# %%
from zef import *
from zef.ops import *
from zef.gql import *
from zef.gql.generate_gql_api import generate_graph_from_file, make_api
from zef.gql.resolvers_utils import *
from schema import schema_gql

wordle_tag = "worduel-api"
g = Graph()
generate_graph_from_file(schema_gql, g)

GraphDelta(
    [
        delegate[(ET.User, RT.Name, AET.String)],
        delegate[(ET.Duel, RT.Participant, ET.User)],
        delegate[(ET.Duel, RT.Game, ET.Game)],
        delegate[(ET.Game, RT.Creator, ET.User)],
        delegate[(ET.Game, RT.Player, ET.User)],
        delegate[(ET.Game, RT.Completed, AET.Bool)],
        delegate[(ET.Game, RT.Solution, AET.String)],
        delegate[(ET.Game, RT.Guess, AET.String)],
    ]
) | g | run


url = "https://raw.githubusercontent.com/charlesreid1/five-letter-words/master/sgb-words.txt"
words = url | make_request | run | get['response_text'] | collect
(ET.WordList, RT.FiveLetters, words) | g | run


############--Mutations--###############
# createUser(name: String): ID
@func(g)
def create_user(name: str, g: VT.Graph, **defaults) -> str:
    r = GraphDelta([
        (ET.User['p1'], RT.Name, name)
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
    def make_return(msg: str = "", game_id: str = "", success: bool = False):
        return {"message": msg, "id": game_id, "success": success}
    solution = to_upper(solution)
    # Creating a game for a duel that doesn't exist
    if duel_id not in g:
        return make_return("Given duel_id doesn't exist in the Graph")
    # Creating a game for a player that doesn't exist
    if creator_id not in g:
        return make_return("Given creator_id doesn't exist in the Graph")

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
        if not last_completed:
            return make_return("Last game in this duel isn't completed yet.")

        # These must exist if we are creating a new game
        if length(last_game >> L[RT.Creator]) != 1:
            return make_return("A creator doesn't exist for last game")
        if length(last_game >> L[RT.Player]) != 1:
            return make_return("A player doesn't exist for last game")

        player = last_game >> RT.Player | collect
        creator = last_game >> RT.Creator | collect

        # The creator must be last game's player
        if creator_id != str(uid(player | to_ezefref)):
            return make_return("Last creator can't create this game.")

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
def accept_duel(duel_id: str, player_id: str, g: VT.Graph, **defaults) -> str:
    connected_games = now(g[duel_id]) >> L[RT.Game]
    if length(connected_games) == 1:       # There must be only one game attached!
        first_game = connected_games | first | collect

        # The player wasn't attached yet
        if length(first_game >> L[RT.Player]) == 0:
            GraphDelta([
                (g[duel_id], RT.Participant, g[player_id]),
                (first_game, RT.Player, g[player_id])
            ]) | g | run

            return str(first_game | to_ezefref | uid | collect)

    return ""


# submitGuess(gameId: ID, guess: String): SubmitGuessReturnType
@func(g)
def submit_guess(game_id, guess, g: VT.Graph, **defaults):
    def make_return(is_eligible: bool = True, solved: bool = False, failed: bool = False, guess_result: list = [], message: str = "", discard_letters: list = []):
        return {"isEligibleGuess": is_eligible, "solved": solved, "failed": failed, "guessResult": guess_result, "message": message, "discardedLetters": discard_letters}

    def make_guess(guess, to_be_guessed):
        discard_letters = set()

        def dispatch_letter(arg):
            i, c = arg
            nonlocal to_be_guessed
            if c == to_be_guessed[i]:
                to_be_guessed = replace_at(i, c.lower(), to_be_guessed)
                return c
            elif c in to_be_guessed:
                to_be_guessed = replace_at(
                    to_be_guessed.rindex(c), c.lower(), to_be_guessed)
                return f"[{c}]"
            else:
                if Not[contains[c.lower()]](to_be_guessed):
                    discard_letters.add(c)
                return "_"

        return (guess
                | enumerate
                | map[dispatch_letter]
                | collect
                ), list(discard_letters)

    if game_id not in g:
        return None
    MAX_GUESSES = 6
    game = now(g[game_id])
    guess = to_upper(guess)

    # Don't continue if this game is already completed
    completed = game >> RT.Completed | collect
    if value(completed):
        return make_return(failed=True, message="This game is already completed.")

    # Early exist if we made correct guess
    solution = game >> RT.Solution | value | collect
    if guess == solution:
        GraphDelta([
            (game, RT.Guess, guess),
            (completed <= True),
        ]) | g | run
        guess_result, discard_letters = make_guess(guess, solution)
        return make_return(guess_result=guess_result, discard_letters=discard_letters, solved=True)

    wordlist_rt = {5: RT.FiveLetters}.get(
        length(solution), RT.FiveLetters)   # Update this
    wordlist = g | all[wordlist_rt] | first | target | now | value | split['\n'] | map[to_upper] | collect
    previous_guesses = game >> L[RT.Guess] | value | collect

    equal_to_length = length | equals[length(solution)]
    in_wordlist = contained_in[wordlist + [solution]]
    not_previous_guess = Not[contained_in[previous_guesses]]
    is_eligible_guess = And[equal_to_length][in_wordlist][not_previous_guess]

    if is_eligible_guess(guess):
        guess_result, discard_letters = make_guess(guess, solution)
        # If this is the last guess
        if len(previous_guesses) == MAX_GUESSES - 1:
            GraphDelta([
                (game, RT.Guess, guess),
                (completed <= True),
            ]) | g | run
            return make_return(guess_result=guess_result, failed=True, discard_letters=discard_letters)
        else:
            GraphDelta([
                (game, RT.Guess, guess),
            ]) | g | run
            return make_return(guess_result=guess_result, discard_letters=discard_letters)
    else:
        if Not[equal_to_length](guess):
            return make_return(is_eligible=False, message=f"Guess isn't {length(solution)} characters long.")
        elif Not[in_wordlist](guess):
            return make_return(is_eligible=False, message=f"Guess isn't in the wordlist.")
        else:
            return make_return(is_eligible=False, message=f"You made this guess before!")

#############--Querys--###############
# getUser(usedId: ID): User
@func(g)
def get_user(user_id: str, g: VT.Graph, **defaults):
    return now(g[user_id])


# getGame(gameId: ID): Game
@func(g)
def get_game(game_id, g: VT.Graph, **defaults):
    return now(g[game_id])

# getDuel(duelId: ID): Duel
@func(g)
def get_duel(duel_id, g: VT.Graph, **defaults):
    return now(g[duel_id])

# getRandomWord(length: Int): String
@func(g)
def get_random_word(length: int, g: VT.Graph, **defaults):
    length = 5
    wordlist_rt = {5: RT.FiveLetters}.get(
        length, RT.FiveLetters)   

    return  random_pick(g | all[wordlist_rt] | first | target | now | value | split['\n'] | map[to_upper] | collect)



#############--Duel Special Logic--###############
@func(g)
def duel_current_game(z: VT.ZefRef, g: VT.Graph, **defaults):
    return z >> L[RT.Game] | last | collect

@func(g)
def duel_current_score(z: VT.ZefRef, g: VT.Graph, **defaults):
    players = dict(z >> L[RT.Participant] | map[lambda u: (value(u >> RT.Name),0)] | collect) 
    def game_score(game):
        if value(game >> RT.Completed):
            player_name = game >> RT.Player >> RT.Name | value | collect
            solution = game >> RT.Solution | value | collect
            guesses = game >> L[RT.Guess] | collect
            if guesses | last | value | to_upper | equals[solution] | collect:
                players[player_name] += 7 - len(guesses)
    z >> L[RT.Game] | for_each[game_score]
    return list(players.items()) | map[lambda kv: {"userName": kv[0], "score": kv[1]}] | collect
    
#----------------------------------------------------------------
schema = gql_schema(g)
types = gql_types_dict(schema)

# DefaultResolversList
default_list = ["CreateGameReturnType", "SubmitGuessReturnType", "Score"] | to_json | collect
(schema, RT.DefaultResolversList, default_list) | g | run


# CustomerSpecificResolvers
specific_resolvers = (
    """def customer_specific_resolvers(ot, ft, bt, rt, fn):
    from zef.ops import now, value, collect
    from zef import RT
    if fn == "id" and now(ft) >> RT.Name | value | collect == "GQL_ID":
       return ("return str(z | to_ezefref | uid | collect)", ["z", "ctx"])
    return ("return None #This means that no resolver is defined!", ["z", "ctx"])
""") | collect
(schema, RT.CustomerSpecificResolvers, specific_resolvers) | g | run


# Mutations Handlers
mutations_dict = {
    "acceptDuel":   accept_duel,
    "createUser":   create_user,
    "createDuel":   create_duel,
    "createGame":   create_game,
    "submitGuess":  submit_guess,
}
connect_zef_function_resolvers(g, types['GQL_Mutation'], mutations_dict)


# Query Handlers
query_dict = {
    "getUser":          get_user,
    "getGame":          get_game,
    "getDuel":          get_duel,
    "getRandomWord":    get_random_word,
}
connect_zef_function_resolvers(g, types['GQL_Query'], query_dict)


# User Handlers
user_dict = {
    "name":  {"triple": (ET.User, RT.Name, AET.String)},
    "duels": {"triple": (ET.Duel, RT.Participant, ET.User), "is_out": False},
}
connect_delegate_resolvers(g, types['GQL_User'], user_dict)


# Duel Handlers
duel_dict = {
    "games":   {"triple": (ET.Duel, RT.Game, ET.Game)},
    "players": {"triple": (ET.Duel, RT.Participant, ET.User)},
}
connect_delegate_resolvers(g, types['GQL_Duel'], duel_dict)
duel_dict = {
    "currentGame":      duel_current_game,
    "currentScore":     duel_current_score,

}
connect_zef_function_resolvers(g, types['GQL_Duel'], duel_dict)

# Game Handlers
game_dict = {
    "player":       {"triple": (ET.Game, RT.Player, ET.User)},
    "creator":      {"triple": (ET.Game, RT.Creator, ET.User)},
    "solution":     {"triple": (ET.Game, RT.Solution, AET.String)},
    "duel":         {"triple": (ET.Duel, RT.Game, ET.Game), "is_out": False},
    "guesses":      {"triple": (ET.Game, RT.Guess, AET.String)},
    "completed":    {"triple": (ET.Game, RT.Completed, AET.Bool)},
}
connect_delegate_resolvers(g, types['GQL_Game'], game_dict)

g | sync[True] | run
g | tag[wordle_tag] | run