#%%
from zef import *
from zef.ops import *
from zef.gql import *
from zef.gql.generate_gql_api import generate_graph_from_file
from zef.gql.resolvers_utils import *
from schema import schema_gql

# Create an empty graph
g = Graph()

# Create a copy of the schema on the graph g we created
generate_graph_from_file(schema_gql, g)


# Create the delegates/blueprint for our data model
[
    delegate_of((ET.User, RT.Name, AET.String)),
    delegate_of((ET.Duel, RT.Participant, ET.User)),
    delegate_of((ET.Duel, RT.Game, ET.Game)),
    delegate_of((ET.Game, RT.Creator, ET.User)),
    delegate_of((ET.Game, RT.Player, ET.User)),
    delegate_of((ET.Game, RT.Completed, AET.Bool)),
    delegate_of((ET.Game, RT.Solution, AET.String)),
    delegate_of((ET.Game, RT.Guess, AET.String)),
] | transact[g] | run


# Retrieve the wordlist and add it as a node on the graph
url = "https://raw.githubusercontent.com/charlesreid1/five-letter-words/master/sgb-words.txt"
words = url | make_request | run | get['response_text'] | collect
(ET.WordList, RT.FiveLetters, words) | g | run
#----------------------------------------------------------------


##########################################
#######Zef Function Resolvers#############
##########################################

############--Mutations--###############
# createUser(name: String): ID
@func(g)
def create_user(name: str, g: VT.Graph, **defaults) -> str:
    r = [
        (ET.User['p1'], RT.Name, name)
    ] | transact[g] | run

    return str(r['p1'] | to_ezefref | uid | collect)


# createDuel(creatorId: ID): ID
@func(g)
def create_duel(creator_id: str, g: VT.Graph, **defaults) -> str:
    r = [
        (ET.Duel['d1'], RT.Participant, g[creator_id]),
    ] | transact[g] | run

    return str(r['d1'] | to_ezefref | uid | collect)


# createGame(solution: String, duelId: ID, creatorId: ID): ID
@func(g)
def create_game(solution: str, duel_id: str, creator_id: str,  g: VT.Graph, **defaults) -> str:
    def make_return(msg: str = "", game_id: str = "", success: bool = False):
        return {"message": msg, "id": game_id, "success": success}
    solution = to_upper_case(solution)
    if len(solution) != 5: return make_return("The solution should be 5 exactly letters long!")

    # Creating a game for a duel that doesn't exist
    if duel_id not in g:
        return make_return("Given duel_id doesn't exist in the Graph")
    # Creating a game for a player that doesn't exist
    if creator_id not in g:
        return make_return("Given creator_id doesn't exist in the Graph")

    duel_games = now(g[duel_id]) >> L[RT.Game]
    if length(duel_games) == 0:
        r = [
            (ET.Game['g1'], RT.Solution,    solution),
            (Z['g1'],       RT.Creator,     g[creator_id]),
            (Z['g1'],       RT.Completed,   False),
            (g[duel_id],    RT.Game,        Z['g1']),
        ] | transact[g] | run

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

        r = [
            (ET.Game['g1'], RT.Solution,    solution),
            (Z['g1'],       RT.Creator,     player),
            (Z['g1'],       RT.Player,      creator),
            (Z['g1'],       RT.Completed,   False),
            (g[duel_id],    RT.Game,        Z['g1']),
        ] | transact[g] | run

    return make_return("", str(r['g1'] | to_ezefref | uid | collect), True)


# acceptDuel(duelId: ID, playerId: ID): Boolean
@func(g)
def accept_duel(duel_id: str, player_id: str, g: VT.Graph, **defaults) -> str:
    connected_games = now(g[duel_id]) >> L[RT.Game]
    if length(connected_games) == 1:       # There must be only one game attached!
        first_game = connected_games | first | collect

        # The player wasn't attached yet
        if length(first_game >> L[RT.Player]) == 0:
            [
                (g[duel_id], RT.Participant, g[player_id]),
                (first_game, RT.Player, g[player_id])
            ] | transact[g] | run

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
                to_be_guessed = replace_at(to_be_guessed, i, c.lower())
                return c
            elif c in to_be_guessed:
                to_be_guessed = replace_at(to_be_guessed, to_be_guessed.rindex(c), c.lower())
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
    guess = to_upper_case(guess)

    # Don't continue if this game is already completed
    completed = game >> RT.Completed | collect
    if value(completed):
        return make_return(failed=True, message="This game is already completed.")

    # Early exist if we made correct guess
    solution = game >> RT.Solution | value | collect
    if guess == solution:
        [
            (game, RT.Guess, guess),
            (completed <= True),
        ] | transact[g] | run
        guess_result, discard_letters = make_guess(guess, solution)
        return make_return(guess_result=guess_result, discard_letters=discard_letters, solved=True)

    # wordlist_rt = {5: RT.FiveLetters}.get(
    #     length(solution), RT.FiveLetters)   # Update this
    # wordlist = g | all[wordlist_rt] | first | target | now | value | split['\n'] | map[to_upper] | collect

    # NOTE This is added here because fetching and parsing the wordlist with each request is costly and slow.
    five_letters = ['CASAS', 'WITHS', 'DODGY', 'SCUDI', 'MUNGS', 'MUONS', 'UREAS', 'IOCTL', 'UNHIP', 'KRONE', 'SAGER', 'VERST', 'EXPAT', 'GRONK', 'UVULA', 'SHAWM', 'BILGY', 'BRAES', 'CENTO', 'WEBBY', 'LIPPY', 'GAMIC', 'LORDY', 'MAZED', 'TINGS', 'SHOAT', 'FAERY', 'WIRER',
'DIAZO', 'CARER', 'RATER', 'GREPS', 'RENTE', 'ZLOTY', 'VIERS', 'UNAPT', 'POOPS', 'FECAL', 'KEPIS', 'TAXON', 'EYERS', 'WONTS', 'SPINA', 'STOAE', 'YENTA', 'POOEY', 'BURET', 'JAPAN', 'BEDEW', 'HAFTS', 'SELFS', 'OARED', 'HERBY', 'PRYER', 'OAKUM', 'DINKS', 'TITTY',
'SEPOY', 'PENES', 'FUSEE', 'WINEY', 'GIMPS', 'NIHIL', 'RILLE', 'GIBER', 'OUSEL', 'UMIAK', 'CUPPY', 'HAMES', 'SHITS', 'AZINE', 'GLADS', 'TACET', 'BUMPH', 'COYER', 'HONKY', 'GAMER', 'GOOKY', 'WASPY', 'SEDGY', 'BENTS', 'VARIA', 'DJINN', 'JUNCO', 'PUBIC', 'WILCO',
'LAZES', 'IDYLS', 'LUPUS', 'RIVES', 'SNOOD', 'SCHMO', 'SPAZZ', 'FINIS', 'NOTER', 'PAVAN', 'ORBED', 'BATES', 'PIPET', 'BADDY', 'GOERS', 'SHAKO', 'STETS', 'SEBUM', 'SEETH', 'LOBAR', 'RAVER', 'AJUGA', 'RICED', 'VELDS', 'DRIBS', 'VILLE', 'DHOWS', 'UNSEW', 'HALMA',
'KRONA', 'LIMBY', 'JIFFS', 'TREYS', 'BAUDS', 'PFFFT', 'MIMER', 'PLEBS', 'CANER', 'JIBER', 'CUPPA', 'WASHY', 'CHUFF', 'UNARM', 'YUKKY', 'STYES', 'WAKER', 'FLAKS', 'MACES', 'RIMES', 'GIMPY', 'GUANO', 'LIRAS', 'KAPOK', 'SCUDS', 'BWANA', 'ORING', 'AIDER', 'PRIER',
'KLUGY', 'MONTE', 'GOLEM', 'VELAR', 'FIRER', 'PIETA', 'UMBEL', 'CAMPO', 'UNPEG', 'FOVEA', 'ABEAM', 'BOSON', 'ASKER', 'GOTHS', 'VOCAB', 'VINED', 'TROWS', 'TIKIS', 'LOPER', 'INDIE', 'BOFFS', 'SPANG', 'GRAPY', 'TATER', 'ICHOR', 'KILTY', 'LOCHS', 'SUPES', 'DEGAS',
'FLICS', 'TORSI', 'BETHS', 'WEBER', 'RESAW', 'LAWNY', 'COVEN', 'MUJIK', 'RELET', 'THERM', 'HEIGH', 'SHNOR', 'TRUED', 'ZAYIN', 'LIEST', 'BARFS', 'BASSI', 'QOPHS', 'ROILY', 'FLABS', 'PUNNY', 'OKRAS', 'HANKS', 'DIPSO', 'NERFS', 'FAUNS', 'CALLA', 'PSEUD', 'LURER',
'MAGUS', 'OBEAH', 'ATRIA', 'TWINK', 'PALMY', 'POCKY', 'PENDS', 'RECTA', 'PLONK', 'SLAWS', 'KEENS', 'NICAD', 'PONES', 'INKER', 'WHEWS', 'GROKS', 'MOSTS', 'TREWS', 'ULNAR', 'GYPPY', 'COCAS', 'EXPOS', 'ERUCT', 'OILER', 'VACUA', 'DRECK', 'DATER', 'ARUMS', 'TUBAL',
'VOXEL', 'DIXIT', 'BEERY', 'ASSAI', 'LADES', 'ACTIN', 'GHOTI', 'BUZZY', 'MEADS', 'GRODY', 'RIBBY', 'CLEWS', 'CREME', 'EMAIL', 'PYXIE', 'KULAK', 'BOCCI', 'RIVED', 'DUDDY', 'HOPER', 'LAPIN', 'WONKS', 'PETRI', 'PHIAL', 'FUGAL', 'HOLON', 'BOOMY', 'DUOMO', 'MUSOS',
'SHIER', 'HAYER', 'PORGY', 'HIVED', 'LITHO', 'FISTY', 'STAGY', 'LUVYA', 'MARIA', 'SMOGS', 'ASANA', 'YOGIC', 'SLOMO', 'FAWNY', 'AMINE', 'WEFTS', 'GONAD', 'TWIRP', 'BRAVA', 'PLYER', 'FERMI', 'LOGES', 'NITER', 'REVET', 'UNATE', 'GYVED', 'TOTTY', 'ZAPPY', 'HONER',
'GIROS', 'DICER', 'CALKS', 'LUXES', 'MONAD', 'CRUFT', 'QUOIN', 'FUMER', 'AMPED', 'SHLEP', 'VINCA', 'YAHOO', 'VULVA', 'ZOOEY', 'DRYAD', 'NIXIE', 'MOPER', 'IAMBS', 'LUNES', 'NUDIE', 'LIMNS', 'WEALS', 'NOHOW', 'MIAOW', 'GOUTS', 'MYNAS', 'MAZER', 'KIKES', 'OXEYE',
'STOUP', 'JUJUS', 'DEBAR', 'PUBES', 'TAELS', 'DEFUN', 'RANDS', 'BLEAR', 'PAVER', 'GOOSY', 'SPROG', 'OLEOS', 'TOFFY', 'PAWER', 'MACED', 'CRITS', 'KLUGE', 'TUBED', 'SAHIB', 'GANEF', 'SCATS', 'SPUTA', 'VANED', 'ACNED', 'TAXOL', 'PLINK', 'OWETH', 'TRIBS', 'RESAY',
'BOULE', 'THOUS', 'HAPLY', 'GLANS', 'MAXIS', 'BEZEL', 'ANTIS', 'PORKS', 'QUOIT', 'ALKYD', 'GLARY', 'BEAMY', 'HEXAD', 'BONKS', 'TECUM', 'KERBS', 'FILAR', 'FRIER', 'REDUX', 'ABUZZ', 'FADER', 'SHOER', 'COUTH', 'TRUES', 'GUYED', 'GOONY', 'BOOKY', 'FUZES', 'HURLY',
'GENET', 'HODAD', 'CALIX', 'FILER', 'PAWLS', 'IODIC', 'UTERO', 'HENGE', 'UNSAY', 'LIERS', 'PIING', 'WEALD', 'SEXED', 'FOLIC', 'POXED', 'CUNTS', 'ANILE', 'KITHS', 'BECKS', 'TATTY', 'PLENA', 'REBAR', 'ABLED', 'TOYER', 'ATTAR', 'TEAKS', 'AIOLI', 'AWING', 'ANENT',
'FECES', 'REDIP', 'WISTS', 'PRATS', 'MESNE', 'MUTER', 'SMURF', 'OWEST', 'BAHTS', 'LOSSY', 'FTPED', 'HUNKY', 'HOERS', 'SLIER', 'SICKS', 'FATLY', 'DELFT', 'HIVER', 'HIMBO', 'PENGO', 'BUSKS', 'LOXES', 'ZONKS', 'ILIUM', 'APORT', 'IKONS', 'MULCT', 'REEVE', 'CIVVY',
'CANNA', 'BARFY', 'KAIAK', 'SCUDO', 'KNOUT', 'GAPER', 'BHANG', 'PEASE', 'UTERI', 'LASES', 'PATEN', 'RASAE', 'AXELS', 'STOAS', 'OMBRE', 'STYLI', 'GUNKY', 'HAZER', 'KENAF', 'AHOYS', 'AMMOS', 'WEENY', 'URGER', 'KUDZU', 'PAREN', 'BOLOS', 'FETOR', 'NITTY', 'TECHY',
'LIETH', 'SOMAS', 'DARKY', 'VILLI', 'GLUON', 'JANES', 'CANTS', 'FARTS', 'SOCLE', 'JINNS', 'RUING', 'SLILY', 'RICER', 'HADDA', 'WOWEE', 'RICES', 'NERTS', 'CAULS', 'SWIVE', 'LILTY', 'MICKS', 'ARITY', 'PASHA', 'FINIF', 'OINKY', 'GUTTY', 'TETRA', 'WISES', 'WOLDS',
'BALDS', 'PICOT', 'WHATS', 'SHIKI', 'BUNGS', 'SNARF', 'LEGOS', 'DUNGS', 'STOGY', 'BERMS', 'TANGS', 'VAILS', 'ROODS', 'MOREL', 'SWARE', 'ELANS', 'LATUS', 'GULES', 'RAZER', 'DOXIE', 'BUENA', 'OVERS', 'GUTTA', 'ZINCS', 'NATES', 'KIRKS', 'TIKES', 'DONEE', 'JERRY',
'MOHEL', 'CEDER', 'DOGES', 'UNMAP', 'FOLIA', 'RAWLY', 'SNARK', 'TOPOI', 'CEILS', 'IMMIX', 'YORES', 'DIEST', 'BUBBA', 'POMPS', 'FORKY', 'TURDY', 'LAWZY', 'POOHS', 'WORTS', 'GLOMS', 'BEANO', 'MULEY', 'BARKY', 'TUNNY', 'AURIC', 'FUNKS', 'GAFFS', 'CORDY', 'CURDY',
'LISLE', 'TORIC', 'SOYAS', 'REMAN', 'MUNGY', 'CARPY', 'APISH', 'OATEN', 'GAPPY', 'AURAE', 'BRACT', 'ROOKY', 'AXLED', 'BURRY', 'SIZER', 'PROEM', 'TURFY', 'IMPRO', 'MASHY', 'MIENS', 'NONNY', 'OLIOS', 'GROOK', 'SATES', 'AGLEY', 'CORGI', 'DASHY', 'DOSER', 'DILDO',
'APSOS', 'XORED', 'LAKER', 'PLAYA', 'SELAH', 'MALTY', 'DULSE', 'FRIGS', 'DEMIT', 'WHOSO', 'RIALS', 'SAWER', 'SPICS', 'BEDIM', 'SNUGS', 'FANIN', 'AZOIC', 'ICERS', 'SUERS', 'WIZEN', 'KOINE', 'TOPOS', 'SHIRR', 'RIFER', 'FERAL', 'LADED', 'LASED', 'TURDS', 'SWEDE',
'EASTS', 'COZEN', 'UNHIT', 'PALLY', 'AITCH', 'SEDUM', 'COPER', 'RUCHE', 'GEEKS', 'SWAGS', 'ETEXT', 'ALGIN', 'OFFED', 'NINJA', 'HOLER', 'DOTER', 'TOTER', 'BESOT', 'DICUT', 'MACER', 'PEENS', 'PEWIT', 'REDOX', 'POLER', 'YECCH', 'FLUKY', 'DOETH', 'TWATS', 'CRUDS',
'BEBUG', 'BIDER', 'STELE', 'HEXER', 'WESTS', 'GLUER', 'PILAU', 'ABAFT', 'WHELM', 'LACER', 'INODE', 'TABUS', 'GATOR', 'CUING', 'REFLY', 'LUTED', 'CUKES', 'BAIRN', 'BIGHT', 'ARSES', 'CRUMP', 'LOGGY', 'BLINI', 'SPOOR', 'TOYON', 'HARKS', 'WAZOO', 'FENNY', 'NAVES',
'KEYER', 'TUFAS', 'MORPH', 'RAJAS', 'TYPAL', 'SPIFF', 'OXLIP', 'UNBAN', 'MUSSY', 'FINNY', 'RIMER', 'LOGIN', 'MOLAS', 'CIRRI', 'HUZZA', 'AGONE', 'UNSEX', 'UNWON', 'PEATS', 'TOILE', 'ZOMBI', 'DEWED', 'NOOKY', 'ALKYL', 'IXNAY', 'DOVEY', 'HOLEY', 'CUBER', 'AMYLS',
'PODIA', 'CHINO', 'APNEA', 'PRIMS', 'LYCRA', 'JOHNS', 'PRIMO', 'FATWA', 'EGGER', 'HEMPY', 'SNOOK', 'HYING', 'FUZED', 'BARMS', 'CRINK', 'MOOTS', 'YERBA', 'RHUMB', 'UNARC', 'DIRER', 'MUNGE', 'ELAND', 'NARES', 'WRIER', 'NODDY', 'ATILT', 'JUKES', 'ENDER', 'THENS',
'UNFIX', 'DOGGO', 'ZOOKS', 'DIDDY', 'SHMOO', 'BRUSK', 'PREST', 'CURER', 'PASTS', 'KELPY', 'BOCCE', 'KICKY', 'TAROS', 'LINGS', 'DICKY', 'NERDY', 'ABEND', 'STELA', 'BIGGY', 'LAVED', 'BALDY', 'PUBIS', 'GOOKS', 'WONKY', 'STIED', 'HYPOS', 'ASSED', 'SPUMY', 'OSIER',
'ROBLE', 'RUMBA', 'BIFFY', 'PUPAL','VIBES', 'GASSY', 'UNLIT', 'NERVY', 'FEMME', 'BITER', 'FICHE', 'BOORS', 'GAFFE', 'SAXES', 'RECAP', 'SYNCH', 'FACIE', 'DICEY', 'OUIJA', 'HEWER', 'LEGIT', 'GURUS', 'EDIFY', 'TWEAK', 'CARON', 'TYPOS', 'RERUN', 'POLLY', 'SURDS',
'HAMZA', 'NULLS', 'HATER', 'LEFTY', 'MOGUL', 'MAFIA', 'DEBUG', 'PATES', 'BLABS', 'SPLAY', 'TALUS', 'PORNO', 'MOOLA', 'NIXED', 'KILOS', 'SNIDE', 'HORSY', 'GESSO', 'JAGGY', 'TROVE', 'NIXES', 'CREEL', 'PATER', 'IOTAS', 'CADGE', 'SKYED', 'HOKUM', 'FURZE', 'ANKHS',
'CURIE', 'NUTSY', 'HILUM', 'REMIX', 'ANGST', 'BURLS', 'JIMMY', 'VEINY', 'TRYST', 'CODON', 'BEFOG', 'GAMED', 'FLUME', 'AXMAN', 'DOOZY', 'LUBES', 'RHEAS', 'BOZOS', 'BUTYL', 'KELLY', 'MYNAH', 'JOCKS', 'DONUT', 'AVIAN', 'WURST', 'CHOCK', 'QUASH', 'QUALS', 'HAYED',
'BOMBE', 'CUSHY', 'SPACY', 'PUKED', 'LEERY', 'THEWS', 'PRINK', 'AMENS', 'TESLA', 'INTRO', 'FIVER', 'FRUMP', 'CAPOS', 'OPINE', 'CODER', 'NAMER', 'JOWLY', 'PUKES', 'HALED', 'CHARD', 'DUFFS', 'BRUIN', 'REUSE', 'WHANG', 'TOONS', 'FRATS', 'SILTY', 'TELEX', 'CUTUP',
'NISEI', 'NEATO', 'DECAF', 'SOFTY', 'BIMBO', 'ADLIB', 'LOONY', 'SHOED', 'AGUES', 'PEEVE', 'NOWAY', 'GAMEY', 'SARGE', 'RERAN', 'EPACT', 'POTTY', 'CONED', 'UPEND', 'NARCO', 'IKATS', 'WHORL', 'JINKS', 'TIZZY', 'WEEPY', 'POSIT', 'MARGE', 'VEGAN', 'CLOPS', 'NUMBS',
'REEKS', 'RUBES', 'ROWER', 'BIPED', 'TIFFS', 'HOCUS', 'HAMMY', 'BUNCO', 'FIXIT', 'TYKES', 'CHAWS', 'YUCKY', 'HOKEY', 'RESEW', 'MAVEN', 'ADMAN', 'SCUZZ', 'SLOGS', 'SOUSE', 'NACHO', 'MIMED', 'MELDS', 'BOFFO', 'DEBIT', 'PINUP', 'VAGUS', 'GULAG', 'RANDY', 'BOSUN',
'EDUCE', 'FAXES', 'AURAS', 'PESTO', 'ANTSY', 'BETAS', 'FIZZY', 'DORKY', 'SNITS', 'MOXIE', 'THANE', 'MYLAR', 'NOBBY', 'GAMIN', 'GOUTY', 'ESSES', 'GOYIM', 'PANED', 'DRUID', 'JADES', 'REHAB', 'GOFER', 'TZARS', 'OCTET', 'HOMED', 'SOCKO', 'DORKS', 'EARED', 'ANTED',
'ELIDE', 'FAZES', 'OXBOW', 'DOWSE', 'SITUS', 'MACAW', 'SCONE', 'DRILY', 'HYPER', 'SALSA', 'MOOCH', 'GATED', 'UNJAM', 'LIPID', 'MITRE', 'VENAL', 'KNISH', 'RITZY', 'DIVAS', 'TORUS', 'MANGE', 'DIMER', 'RECUT', 'MESON', 'WINED', 'FENDS', 'PHAGE', 'FIATS', 'CAULK',
'CAVIL', 'PANTY', 'ROANS', 'BILKS', 'HONES', 'BOTCH', 'ESTOP', 'SULLY', 'SOOTH', 'GELDS', 'AHOLD', 'RAPER', 'PAGER', 'FIXER', 'INFIX', 'HICKS', 'TUXES', 'PLEBE', 'TWITS', 'ABASH', 'TWIXT', 'WACKO', 'PRIMP', 'NABLA', 'GIRTS', 'MIFFS', 'EMOTE', 'XEROX', 'REBID',
'SHAHS', 'RUTTY', 'GROUT', 'GRIFT', 'DEIFY', 'BIDDY', 'KOPEK', 'SEMIS', 'BRIES', 'ACMES', 'PITON', 'HUSSY', 'TORTS', 'DISCO', 'WHORE', 'BOOZY', 'GIBED', 'VAMPS', 'AMOUR', 'SOPPY', 'GONZO', 'DURST', 'WADER', 'TUTUS', 'PERMS', 'CATTY', 'GLITZ', 'BRIGS', 'NERDS',
'BARMY', 'GIZMO', 'OWLET', 'SAYER', 'MOLLS', 'SHARD', 'WHOPS', 'COMPS', 'CORER', 'COLAS', 'MATTE', 'DROID', 'PLOYS', 'VAPID', 'CAIRN', 'DEISM', 'MIXUP', 'YIKES', 'PROSY', 'RAKER', 'FLUBS', 'WHISH', 'REIFY', 'CRAPS', 'SHAGS', 'CLONE', 'HAZED', 'MACHO', 'RECTO',
'REFIX', 'DRAMS', 'BIKER', 'AQUAS', 'PORKY', 'DOYEN', 'EXUDE', 'GOOFS', 'DIVVY', 'NOELS', 'JIVED', 'HULKY', 'CAGER', 'HARPY', 'OLDIE', 'VIVAS', 'ADMIX', 'CODAS', 'ZILCH', 'DEIST', 'ORCAS', 'RETRO', 'PILAF', 'PARSE', 'RANTS', 'ZINGY', 'TODDY', 'CHIFF', 'MICRO',
'VEEPS', 'GIRLY', 'NEXUS', 'DEMOS', 'BIBBS', 'ANTES', 'LULUS', 'GNARL', 'ZIPPY', 'IVIED', 'EPEES', 'WIMPS', 'TROMP', 'GRAIL', 'YOYOS', 'POUFS', 'HALES', 'ROUST', 'CABAL', 'RAWER', 'PAMPA', 'MOSEY', 'KEFIR', 'BURGS', 'UNMET', 'CUSPY', 'BOOBS', 'BOONS', 'HYPES',
'DYNES', 'NARDS', 'LANAI', 'YOGIS', 'SEPAL', 'QUARK', 'TOKED', 'PRATE', 'AYINS', 'HAWED', 'SWIGS', 'VITAS', 'TOKER', 'DOPER', 'BOSSA', 'LINTY', 'FOIST', 'MONDO', 'STASH', 'KAYOS', 'TWERP', 'ZESTY', 'CAPON', 'WIMPY', 'REWED', 'FUNGO', 'TAROT', 'FROSH', 'KABOB',
'PINKO', 'REDID', 'MIMEO', 'HEIST', 'TARPS', 'LAMAS', 'SUTRA', 'DINAR', 'WHAMS', 'BUSTY', 'SPAYS', 'MAMBO', 'NABOB', 'PREPS', 'ODOUR', 'CABBY', 'CONKS', 'SLUFF', 'DADOS', 'HOURI', 'SWART', 'BALMS', 'GUTSY', 'FAXED', 'EGADS', 'PUSHY', 'RETRY', 'AGORA', 'DRUBS',
'DAFFY', 'CHITS', 'MUFTI', 'KARMA', 'LOTTO', 'TOFFS', 'BURPS', 'DEUCE', 'ZINGS', 'KAPPA', 'CLADS', 'DOGGY', 'DUPER', 'SCAMS', 'OGLER', 'MIMES', 'THROE', 'ZETAS', 'WALED', 'PROMO', 'BLATS', 'MUFFS', 'OINKS', 'VIAND', 'COSET', 'FINKS', 'FADDY', 'MINIS', 'SNAFU',
'SAUNA', 'USURY', 'MUXES', 'CRAWS', 'STATS', 'CONDO', 'COXES', 'LOOPY', 'DORMS', 'ASCOT', 'DIPPY', 'EXECS', 'DOPEY', 'ENVOI', 'UMPTY', 'GISMO', 'FAZED', 'STROP', 'JIVES', 'SLIMS', 'BATIK', 'PINGS', 'SONLY', 'LEGGO', 'PEKOE', 'PRAWN', 'LUAUS', 'CAMPY', 'OODLE',
'PREXY', 'PROMS', 'TOUTS', 'OGLES', 'TWEET', 'TOADY', 'NAIAD', 'HIDER', 'NUKED', 'FATSO', 'SLUTS', 'OBITS', 'NARCS', 'TYROS', 'DELIS', 'WOOER', 'HYPED', 'POSET', 'BYWAY', 'TEXAS', 'SCROD', 'AVOWS', 'FUTON', 'TORTE', 'TUPLE', 'CAROM', 'KEBAB', 'TAMPS', 'JILTS',
'DUALS', 'ARTSY', 'REPRO', 'MODEM', 'TOPED', 'PSYCH', 'SICKO', 'KLUTZ', 'TARNS', 'COXED', 'DRAYS', 'CLOYS', 'ANDED', 'PIKER', 'AIMER', 'SURAS', 'LIMOS', 'FLACK', 'HAPAX', 'DUTCH', 'MUCKY', 'SHIRE', 'KLIEG', 'STAPH', 'LAYUP', 'TOKES', 'AXING', 'TOPER', 'DUVET',
'COWRY', 'PROFS', 'BLAHS', 'ADDLE', 'SUDSY', 'BATTY', 'COIFS', 'SUETY', 'GABBY', 'HAFTA', 'PITAS', 'GOUDA', 'DEICE', 'TAUPE', 'TOPES', 'DUCHY', 'NITRO', 'CARNY', 'LIMEY', 'ORALS', 'HIRER', 'TAXER', 'ROILS', 'RUBLE', 'ELATE', 'DOLOR', 'WRYER', 'SNOTS', 'QUAIS',
'COKED', 'GIMEL', 'GORSE', 'MINAS', 'GOEST', 'AGAPE', 'MANTA', 'JINGS', 'ILIAC', 'ADMEN', 'OFFEN', 'CILLS', 'OFFAL', 'LOTTA', 'BOLAS', 'THWAP', 'ALWAY', 'BOGGY', 'DONNA', 'LOCOS', 'BELAY', 'GLUEY', 'BITSY', 'MIMSY', 'HILAR', 'OUTTA', 'VROOM', 'FETAL', 'RATHS',
'RENAL', 'DYADS', 'CROCS', 'VIRES', 'CULPA', 'KIVAS', 'FEIST', 'TEATS', 'THATS', 'YAWLS', 'WHENS', 'ABACA', 'OHHHH', 'APHIS', 'FUSTY', 'ECLAT', 'PERDU', 'MAYST', 'EXEAT', 'MOLLY', 'SUPRA', 'WETLY', 'PLASM', 'BUFFA', 'SEMEN', 'PUKKA', 'TAGUA', 'PARAS', 'STOAT',
'SECCO', 'CARTE', 'HAUTE', 'MOLAL', 'SHADS', 'FORMA', 'OVOID', 'PIONS', 'MODUS', 'BUENO', 'RHEUM', 'SCURF', 'PARER', 'EPHAH', 'DOEST', 'SPRUE', 'FLAMS', 'MOLTO', 'DIETH', 'CHOOS', 'MIKED', 'BRONX', 'GOOPY', 'BALLY', 'PLUMY', 'MOONY', 'MORTS', 'YOURN', 'BIPOD',
'SPUME', 'ALGAL', 'AMBIT', 'MUCHO', 'SPUED', 'DOZER', 'HARUM', 'GROAT', 'SKINT', 'LAUDE', 'THRUM', 'PAPPY', 'ONCET', 'RIMED', 'GIGUE', 'LIMED', 'PLEIN', 'REDLY', 'HUMPF', 'LITES', 'SEEST', 'GREBE', 'ABSIT', 'THANX', 'PSHAW', 'YAWPS', 'PLATS', 'PAYED', 'AREAL',
'TILTH', 'YOUSE', 'GWINE', 'THEES', 'WATSA', 'LENTO', 'SPITZ', 'YAWED', 'GIPSY', 'SPRAT', 'CORNU', 'AMAHS', 'BLOWY', 'WAHOO', 'LUBRA', 'MECUM', 'WHOOO', 'COQUI', 'SABRA', 'EDEMA', 'MRADS', 'DICOT', 'ASTRO', 'KITED', 'OUZEL', 'DIDOS', 'GRATA', 'BONNE', 'AXMEN',
'KLUNK', 'SUMMA', 'LAVES', 'PURLS', 'YAWNY', 'TEARY', 'MASSE', 'LARGO', 'BAZAR', 'PSSST', 'SYLPH', 'LULAB', 'TOQUE', 'FUGIT', 'PLUNK', 'ORTHO', 'LUCRE', 'COOCH', 'WHIPT', 'FOLKY', 'TYRES', 'WHEEE', 'CORKY', 'INJUN', 'SOLON', 'DIDOT', 'KERFS', 'RAYED', 'WASSA',
'CHILE', 'BEGAT', 'NIPPY', 'LITRE', 'MAGNA', 'REBOX', 'HYDRO', 'MILCH', 'BRENT', 'GYVES', 'LAZED', 'FEUED', 'MAVIS', 'INAPT', 'BAULK', 'CASUS', 'SCRUM', 'WISED', 'FOSSA', 'DOWER', 'KYRIE', 'BHOYS', 'SCUSE', 'FEUAR', 'OHMIC', 'JUSTE', 'UKASE', 'BEAUX', 'TUSKY',
'ORATE', 'MUSTA', 'LARDY', 'INTRA', 'QUIFF', 'EPSOM', 'NEATH', 'OCHER', 'TARED', 'HOMME', 'MEZZO', 'CORMS', 'PSOAS', 'BEAKY', 'TERRY', 'INFRA', 'SPIVS', 'TUANS', 'BELLI', 'BERGS', 'ANIMA', 'WEIRS', 'MAHUA', 'SCOPS', 'MANSE', 'TITRE', 'CURIA', 'KEBOB', 'CYCAD',
'TALKY', 'FUCKS', 'TAPIS', 'AMIDE', 'DOLCE', 'SLOES', 'JAKES', 'RUSSE', 'BLASH', 'TUTTI', 'PRUTA', 'PANGA', 'BLEBS', 'TENCH', 'SWARF', 'HEREM', 'MISSY', 'MERSE', 'PAWKY', 'LIMEN', 'VIVRE', 'CHERT', 'UNSEE', 'TIROS', 'BRACK', 'FOOTS', 'WELSH', 'FOSSE', 'KNOPS',
'ILEUM', 'NOIRE', 'FIRMA', 'PODGY', 'LAIRD', 'THUNK', 'SHUTE', 'ROWAN', 'SHOJI', 'POESY', 'UNCAP', 'FAMES', 'GLEES', 'COSTA', 'TURPS', 'FORES', 'SOLUM', 'IMAGO', 'BYRES', 'FONDU', 'CONEY', 'POLIS', 'DICTU', 'KRAAL', 'SHERD', 'MUMBO', 'WROTH', 'CHARS', 'UNBOX',
'VACUO', 'SLUED', 'WEEST', 'HADES', 'WILED', 'SYNCS', 'MUSER', 'EXCON', 'HOARS', 'SIBYL', 'PASSE', 'JOEYS', 'LOTSA', 'LEPTA', 'SHAYS', 'BOCKS', 'ENDUE', 'DARER', 'NONES', 'ILEUS', 'PLASH', 'BUSBY', 'WHEAL', 'BUFFO', 'YOBBO', 'BILES', 'POXES', 'ROOTY', 'LICIT',
'TERCE', 'BROMO', 'HAYEY', 'DWEEB', 'IMBED', 'SARAN', 'BRUIT', 'PUNKY', 'SOFTS', 'BIFFS', 'LOPPY', 'AGARS', 'AQUAE', 'LIVRE', 'BIOME', 'BUNDS', 'SHEWS', 'DIEMS', 'GINNY', 'DEGUM', 'POLOS', 'DESEX', 'UNMAN', 'DUNGY', 'VITAM', 'WEDGY', 'GLEBE', 'APERS', 'RIDGY',
'ROIDS', 'WIFEY', 'VAPES', 'WHOAS', 'BUNKO', 'YOLKY', 'ULNAS', 'REEKY', 'BODGE', 'BRANT', 'DAVIT', 'DEQUE', 'LIKER', 'JENNY', 'TACTS', 'FULLS', 'TREAP', 'LIGNE', 'ACKED', 'REFRY', 'VOWER', 'AARGH', 'CHURL', 'MOMMA', 'GAOLS', 'WHUMP', 'ARRAS', 'MARLS', 'TILER',
'GROGS', 'MEMES', 'MIDIS', 'TIDED', 'HALER', 'DUCES', 'TWINY', 'POSTE', 'UNRIG', 'PRISE', 'DRABS', 'QUIDS', 'FACER', 'SPIER', 'BARIC', 'GEOID', 'REMAP', 'TRIER', 'GUNKS', 'STENO', 'STOMA', 'AIRER', 'OVATE', 'TORAH', 'APIAN', 'SMUTS', 'POCKS', 'YURTS', 'EXURB',
'DEFOG', 'NUDER', 'BOSKY', 'NIMBI', 'MOTHY', 'JOYED', 'LABIA', 'PARDS', 'JAMMY', 'BIGLY', 'FAXER', 'HOPPY', 'NURBS', 'COTES', 'DISHY', 'VISED', 'CELEB', 'PISMO','PALLS', 'MOPES', 'BONED', 'WISPY', 'RAVED', 'SWAPS', 'JUNKY', 'DOILY', 'PAWNS', 'TAMER', 'POACH',
'BAITS', 'DAMNS', 'GUMBO', 'DAUNT', 'PRANK', 'HUNKS', 'BUXOM', 'HERES', 'HONKS', 'STOWS', 'UNBAR', 'IDLES', 'ROUTS', 'SAGES', 'GOADS', 'REMIT', 'COPES', 'DEIGN', 'CULLS', 'GIRDS', 'HAVES', 'LUCKS', 'STUNK', 'DODOS', 'SHAMS', 'SNUBS', 'ICONS', 'USURP', 'DOOMS',
'HELLS', 'SOLED', 'COMAS', 'PAVES', 'MATHS', 'PERKS', 'LIMPS', 'WOMBS', 'BLURB', 'DAUBS', 'COKES', 'SOURS', 'STUNS', 'CASED', 'MUSTS', 'COEDS', 'COWED', 'APING', 'ZONED', 'RUMMY', 'FETES', 'SKULK', 'QUAFF', 'RAJAH', 'DEANS', 'REAPS', 'GALAS', 'TILLS', 'ROVED',
'KUDOS', 'TONED', 'PARED', 'SCULL', 'VEXES', 'PUNTS', 'SNOOP', 'BAILS', 'DAMES', 'HAZES', 'LORES', 'MARTS', 'VOIDS', 'AMEBA', 'RAKES', 'ADZES', 'HARMS', 'REARS', 'SATYR', 'SWILL', 'HEXES', 'COLIC', 'LEEKS', 'HURLS', 'YOWLS', 'IVIES', 'PLOPS', 'MUSKS', 'PAPAW',
'JELLS', 'BUSED', 'CRUET', 'BIDED', 'FILCH', 'ZESTS', 'ROOKS', 'LAXLY', 'RENDS', 'LOAMS', 'BASKS', 'SIRES', 'CARPS', 'POKEY', 'FLITS', 'MUSES', 'BAWLS', 'SHUCK', 'VILER', 'LISPS', 'PEEPS', 'SORER', 'LOLLS', 'PRUDE', 'DIKED', 'FLOSS', 'FLOGS', 'SCUMS', 'DOPES',
'BOGIE', 'PINKY', 'LEAFS', 'TUBAS', 'SCADS', 'LOWED', 'YESES', 'BIKED', 'QUALM', 'EVENS', 'CANED', 'GAWKS', 'WHITS', 'WOOLY', 'GLUTS', 'ROMPS', 'BESTS', 'DUNCE', 'CRONY', 'JOIST', 'TUNAS', 'BONER', 'MALLS', 'PARCH', 'AVERS', 'CRAMS', 'PARES', 'DALLY', 'BIGOT',
'KALES', 'FLAYS', 'LEACH', 'GUSHY', 'POOCH', 'HUGER', 'SLYER', 'GOLFS', 'MIRES', 'FLUES', 'LOAFS', 'ARCED', 'ACNES', 'NEONS', 'FIEFS', 'DINTS', 'DAZES', 'POUTS', 'CORED', 'YULES', 'LILTS', 'BEEFS', 'MUTTS', 'FELLS', 'COWLS', 'SPUDS', 'LAMES', 'JAWED', 'DUPES',
'DEADS', 'BYLAW', 'NOONS', 'NIFTY', 'CLUED', 'VIREO', 'GAPES', 'METES', 'CUTER', 'MAIMS', 'DROLL', 'CUPID', 'MAULS', 'SEDGE', 'PAPAS', 'WHEYS', 'EKING', 'LOOTS', 'HILTS', 'MEOWS', 'BEAUS', 'DICES', 'PEPPY', 'RIPER', 'FOGEY', 'GISTS', 'YOGAS', 'GILTS', 'SKEWS',
'CEDES', 'ZEALS', 'ALUMS', 'OKAYS', 'ELOPE', 'GRUMP', 'WAFTS', 'SOOTS', 'BLIMP', 'HEFTS', 'MULLS', 'HOSED', 'CRESS', 'DOFFS', 'RUDER', 'PIXIE', 'WAIFS', 'OUSTS', 'PUCKS', 'BIERS', 'GULCH', 'SUETS', 'HOBOS', 'LINTS', 'BRANS', 'TEALS', 'GARBS', 'PEWEE', 'HELMS',
'TURFS', 'QUIPS', 'WENDS', 'BANES', 'NAPES', 'ICIER', 'SWATS', 'BAGEL', 'HEXED', 'OGRES', 'GONER', 'GILDS', 'PYRES', 'LARDS', 'BIDES', 'PAGED', 'TALON', 'FLOUT', 'MEDIC', 'VEALS', 'PUTTS', 'DIRKS', 'DOTES', 'TIPPY', 'BLURT', 'PITHS', 'ACING', 'BARER', 'WHETS',
'GAITS', 'WOOLS', 'DUNKS', 'HEROS', 'SWABS', 'DIRTS', 'JUTES', 'HEMPS', 'SURFS', 'OKAPI', 'CHOWS', 'SHOOS', 'DUSKS', 'PARRY', 'DECAL', 'FURLS', 'CILIA', 'SEARS', 'NOVAE', 'MURKS', 'WARPS', 'SLUES', 'LAMER', 'SARIS', 'WEANS', 'PURRS', 'DILLS', 'TOGAS', 'NEWTS',
'MEANY', 'BUNTS', 'RAZES', 'GOONS', 'WICKS', 'RUSES', 'VENDS', 'GEODE', 'DRAKE', 'JUDOS', 'LOFTS', 'PULPS', 'LAUDS', 'MUCKS', 'VISES', 'MOCHA', 'OILED', 'ROMAN', 'ETHYL', 'GOTTA', 'FUGUE', 'SMACK', 'GOURD', 'BUMPY', 'RADIX', 'FATTY', 'BORAX', 'CUBIT', 'CACTI',
'GAMMA', 'FOCAL', 'AVAIL', 'PAPAL', 'GOLLY', 'ELITE', 'VERSA', 'BILLY', 'ADIEU', 'ANNUM', 'HOWDY', 'RHINO', 'NORMS', 'BOBBY', 'AXIOM', 'SETUP', 'YOLKS', 'TERNS', 'MIXER', 'GENRE', 'KNOLL', 'ABODE', 'JUNTA', 'GORGE', 'COMBO', 'ALPHA', 'OVERT', 'KINDA', 'SPELT',
'PRICK', 'NOBLY', 'EPHOD', 'AUDIO', 'MODAL', 'VELDT', 'WARTY', 'FLUKE', 'BONNY', 'BREAM', 'ROSIN', 'BOLLS', 'DOERS', 'DOWNS', 'BEADY', 'MOTIF', 'HUMPH', 'FELLA', 'MOULD', 'CREPE', 'KERNS', 'ALOHA', 'GLYPH', 'AZURE', 'RISER', 'BLEST', 'LOCUS', 'LUMPY', 'BERYL',
'WANNA', 'BRIER', 'TUNER', 'ROWDY', 'MURAL', 'TIMER', 'CANST', 'KRILL', 'QUOTH', 'LEMME', 'TRIAD', 'TENON', 'AMPLY', 'DEEPS', 'PADRE', 'LEANT', 'PACER', 'OCTAL', 'DOLLY', 'TRANS', 'SUMAC', 'FOAMY', 'LOLLY', 'GIVER', 'QUIPU', 'CODEX', 'MANNA', 'UNWED', 'VODKA',
'FERNY', 'SALON', 'DUPLE', 'BORON', 'REVUE', 'CRIER', 'ALACK', 'INTER', 'DILLY', 'WHIST', 'CULTS', 'SPAKE', 'RESET', 'LOESS', 'DECOR', 'MOVER', 'VERVE', 'ETHIC', 'GAMUT', 'LINGO', 'DUNNO', 'ALIGN', 'SISSY', 'INCUR', 'REEDY', 'AVANT', 'PIPER', 'WAXER', 'CALYX',
'BASIL', 'COONS', 'SEINE', 'PINEY', 'LEMMA', 'TRAMS', 'WINCH', 'WHIRR', 'SAITH', 'IONIC', 'HEADY', 'HAREM', 'TUMMY', 'SALLY', 'SHIED', 'DROSS', 'FARAD', 'SAVER', 'TILDE', 'JINGO', 'BOWER', 'SERIF', 'FACTO', 'BELLE', 'INSET', 'BOGUS', 'CAVED', 'FORTE', 'SOOTY',
'BONGO', 'TOVES', 'CREDO', 'BASAL', 'YELLA', 'AGLOW', 'GLEAN', 'GUSTO', 'HYMEN', 'ETHOS', 'TERRA', 'BRASH', 'SCRIP', 'SWASH', 'ALEPH', 'TINNY', 'ITCHY', 'WANTA', 'TRICE', 'JOWLS', 'GONGS', 'GARDE', 'BORIC', 'TWILL', 'SOWER', 'HENRY', 'AWASH', 'LIBEL', 'SPURN',
'SABRE', 'REBUT', 'PENAL', 'OBESE', 'SONNY', 'QUIRT', 'MEBBE', 'TACIT', 'GREEK', 'XENON', 'HULLO', 'PIQUE', 'ROGER', 'NEGRO', 'HADST', 'GECKO', 'BEGET', 'UNCUT', 'ALOES', 'LOUIS', 'QUINT', 'CLUNK', 'RAPED', 'SALVO', 'DIODE', 'MATEY', 'HERTZ', 'XYLEM', 'KIOSK',
'APACE', 'CAWED', 'PETER', 'WENCH', 'COHOS', 'SORTA', 'GAMBA', 'BYTES', 'TANGO', 'NUTTY', 'AXIAL', 'ALECK', 'NATAL', 'CLOMP', 'GORED', 'SIREE', 'BANDY', 'GUNNY', 'RUNIC', 'WHIZZ', 'RUPEE', 'FATED', 'WIPER', 'BARDS', 'BRINY', 'STAID', 'HOCKS', 'OCHRE', 'YUMMY',
'GENTS', 'SOUPY', 'ROPER', 'SWATH', 'CAMEO', 'EDGER', 'SPATE', 'GIMME', 'EBBED', 'BREVE', 'THETA', 'DEEMS', 'DYKES', 'SERVO', 'TELLY', 'TABBY', 'TARES', 'BLOCS', 'WELCH', 'GHOUL', 'VITAE', 'CUMIN', 'DINKY', 'BRONC', 'TABOR', 'TEENY', 'COMER', 'BORER', 'SIRED',
'PRIVY', 'MAMMY', 'DEARY', 'GYROS', 'SPRIT', 'CONGA', 'QUIRE', 'THUGS', 'FUROR', 'BLOKE', 'RUNES', 'BAWDY', 'CADRE', 'TOXIN', 'ANNUL', 'EGGED', 'ANION', 'NODES', 'PICKY', 'STEIN', 'JELLO', 'AUDIT', 'ECHOS', 'FAGOT', 'LETUP', 'EYRIE', 'FOUNT', 'CAPED', 'AXONS',
'AMUCK', 'BANAL', 'RILED', 'PETIT', 'UMBER', 'MILER', 'FIBRE', 'AGAVE', 'BATED', 'BILGE', 'VITRO', 'FEINT', 'PUDGY', 'MATER', 'MANIC', 'UMPED', 'PESKY', 'STREP', 'SLURP', 'PYLON', 'PUREE', 'CARET', 'TEMPS', 'NEWEL', 'YAWNS', 'SEEDY', 'TREED', 'COUPS', 'RANGY',
'BRADS', 'MANGY', 'LONER', 'CIRCA', 'TIBIA', 'AFOUL', 'MOMMY', 'TITER', 'CARNE', 'KOOKY', 'MOTES', 'AMITY', 'SUAVE', 'HIPPO', 'CURVY', 'SAMBA', 'NEWSY', 'ANISE', 'IMAMS', 'TULLE', 'AWAYS', 'LIVEN', 'HALLO', 'WALES', 'OPTED', 'CANTO', 'IDYLL', 'BODES', 'CURIO',
'WRACK', 'HIKER', 'CHIVE', 'YOKEL', 'DOTTY', 'DEMUR', 'CUSPS', 'SPECS', 'QUADS', 'LAITY', 'TONER', 'DECRY', 'WRITS', 'SAUTE', 'CLACK', 'AUGHT', 'LOGOS', 'TIPSY', 'NATTY', 'DUCAL', 'BIDET', 'BULGY', 'METRE', 'LUSTS', 'UNARY', 'GOETH', 'BALER', 'SITED', 'SHIES',
'HASPS', 'BRUNG', 'HOLED', 'SWANK', 'LOOKY', 'MELEE', 'HUFFY', 'LOAMY', 'PIMPS', 'TITAN', 'BINGE', 'SHUNT', 'FEMUR', 'LIBRA', 'SEDER', 'HONED', 'ANNAS', 'COYPU', 'SHIMS', 'ZOWIE', 'JIHAD', 'SAVVY', 'NADIR', 'BASSO', 'MONIC', 'MANED', 'MOUSY', 'OMEGA', 'LAVER',
'PRIMA', 'PICAS', 'FOLIO', 'MECCA', 'REALS', 'TROTH', 'TESTY', 'BALKY', 'CRIMP', 'CHINK', 'ABETS', 'SPLAT', 'ABACI', 'VAUNT', 'CUTIE', 'PASTY', 'MORAY', 'LEVIS', 'RATTY', 'ISLET', 'JOUST', 'MOTET', 'VIRAL', 'NUKES', 'GRADS', 'COMFY', 'VOILA', 'WOOZY', 'BLUED',
'WHOMP', 'SWARD', 'METRO', 'SKEET', 'CHINE', 'AERIE', 'BOWIE', 'TUBBY', 'EMIRS', 'COATI', 'UNZIP', 'SLOBS', 'TRIKE', 'FUNKY', 'DUCAT', 'DEWEY', 'SKOAL', 'WADIS', 'OOMPH', 'TAKER', 'MINIM', 'GETUP', 'STOIC', 'SYNOD', 'RUNTY', 'FLYBY', 'BRAZE', 'INLAY', 'VENUE',
'LOUTS', 'PEATY', 'ORLON', 'HUMPY', 'RADON', 'BEAUT', 'RASPY', 'UNFED', 'CRICK', 'NAPPY', 'VIZOR', 'YIPES', 'REBUS', 'DIVOT', 'KIWIS', 'VETCH', 'SQUIB', 'SITAR', 'KIDDO', 'DYERS', 'COTTA', 'MATZO', 'LAGER', 'ZEBUS', 'CRASS', 'DACHA', 'KNEED', 'DICTA', 'FAKIR',
'KNURL', 'RUNNY', 'UNPIN', 'JULEP', 'GLOBS', 'NUDES', 'SUSHI', 'TACKY', 'STOKE', 'KAPUT', 'BUTCH', 'HULAS', 'CROFT', 'ACHOO', 'GENII', 'NODAL', 'OUTGO', 'SPIEL', 'VIOLS', 'FETID', 'CAGEY', 'FUDGY', 'EPOXY', 'LEGGY', 'HANKY', 'LAPIS', 'FELON', 'BEEFY', 'COOTS',
'MELBA', 'CADDY', 'SEGUE', 'BETEL', 'FRIZZ', 'DREAR', 'KOOKS', 'TURBO', 'HOAGY', 'MOULT', 'HELIX', 'ZONAL', 'ARIAS', 'NOSEY', 'PAEAN', 'LACEY', 'BANNS', 'SWAIN', 'FRYER', 'RETCH', 'TENET', 'GIGAS', 'WHINY', 'OGLED', 'RUMEN', 'BEGOT', 'CRUSE', 'ABUTS', 'RIVEN',
'BALKS', 'SINES', 'SIGMA', 'ABASE', 'ENNUI', 'GORES', 'UNSET', 'AUGUR', 'SATED', 'ODIUM', 'LATIN', 'DINGS', 'MOIRE', 'SCION', 'HENNA', 'KRAUT', 'DICKS', 'LIFER', 'PRIGS', 'BEBOP', 'GAGES', 'GAZER', 'FANNY', 'GIBES', 'AURAL', 'TEMPI', 'HOOCH', 'RAPES', 'SNUCK',
'HARTS', 'TECHS', 'EMEND', 'NINNY', 'GUAVA', 'SCARP', 'LIEGE', 'TUFTY', 'SEPIA', 'TOMES', 'CAROB', 'EMCEE', 'PRAMS', 'POSER', 'VERSO', 'HUBBA', 'JOULE', 'BAIZE', 'BLIPS', 'SCRIM', 'CUBBY', 'CLAVE', 'WINOS', 'REARM', 'LIENS', 'LUMEN', 'CHUMP', 'NANNY', 'TRUMP',
'FICHU', 'CHOMP', 'HOMOS', 'PURTY', 'MASER', 'WOOSH', 'PATSY', 'SHILL', 'RUSKS', 'AVAST', 'SWAMI', 'BODED', 'AHHHH', 'LOBED', 'NATCH', 'SHISH', 'TANSY', 'SNOOT', 'PAYER', 'ALTHO', 'SAPPY', 'LAXER', 'HUBBY', 'AEGIS', 'RILES', 'DITTO', 'JAZZY', 'DINGO', 'QUASI',
'SEPTA', 'PEAKY', 'LORRY', 'HEERD', 'BITTY', 'PAYEE', 'SEAMY', 'APSES', 'IMBUE', 'BELIE', 'CHARY', 'SPOOF', 'PHYLA', 'CLIME', 'BABEL', 'WACKY', 'SUMPS', 'SKIDS', 'KHANS', 'CRYPT', 'INURE', 'NONCE', 'OUTEN', 'FAIRE', 'HOOEY', 'ANOLE', 'KAZOO', 'CALVE', 'LIMBO',
'ARGOT', 'DUCKY', 'FAKER','GNATS', 'BOUTS', 'SISAL', 'SHUTS', 'HOSES', 'DRYLY', 'HOVER', 'GLOSS', 'SEEPS', 'DENIM', 'PUTTY', 'GUPPY', 'LEAKY', 'DUSKY', 'FILTH', 'OBOES', 'SPANS', 'FOWLS', 'ADORN', 'GLAZE', 'HAUNT', 'DARES', 'OBEYS', 'BAKES', 'ABYSS', 'SMELT',
'GANGS', 'ACHES', 'TRAWL', 'CLAPS', 'UNDID', 'SPICY', 'HOIST', 'FADES', 'VICAR', 'ACORN', 'PUSSY', 'GRUFF', 'MUSTY', 'TARTS', 'SNUFF', 'HUNCH', 'TRUCE', 'TWEED', 'DRYER', 'LOSER', 'SHEAF', 'MOLES', 'LAPSE', 'TAWNY', 'VEXED', 'AUTOS', 'WAGER', 'DOMES', 'SHEEN',
'CLANG', 'SPADE', 'SOWED', 'BROIL', 'SLYLY', 'STUDS', 'GRUNT', 'DONOR', 'SLUGS', 'ASPEN', 'HOMER', 'CROAK', 'TITHE', 'HALTS', 'AVERT', 'HAVOC', 'HOGAN', 'GLINT', 'RUDDY', 'JEEPS', 'FLAKY', 'LADLE', 'TAUNT', 'SNORE', 'FINES', 'PROPS', 'PRUNE', 'PESOS', 'RADII',
'POKES', 'TILED', 'DAISY', 'HERON', 'VILLA', 'FARCE', 'BINDS', 'CITES', 'FIXES', 'JERKS', 'LIVID', 'WAKED', 'INKED', 'BOOMS', 'CHEWS', 'LICKS', 'HYENA', 'SCOFF', 'LUSTY', 'SONIC', 'SMITH', 'USHER', 'TUCKS', 'VIGIL', 'MOLTS', 'SECTS', 'SPARS', 'DUMPS', 'SCALY',
'WISPS', 'SORES', 'MINCE', 'PANDA', 'FLIER', 'AXLES', 'PLIED', 'BOOBY', 'PATIO', 'RABBI', 'PETAL', 'POLYP', 'TINTS', 'GRATE', 'TROLL', 'TOLLS', 'RELIC', 'PHONY', 'BLEAT', 'FLAWS', 'FLAKE', 'SNAGS', 'APTLY', 'DRAWL', 'ULCER', 'SOAPY', 'BOSSY', 'MONKS', 'CRAGS',
'CAGED', 'TWANG', 'DINER', 'TAPED', 'CADET', 'GRIDS', 'SPAWN', 'GUILE', 'NOOSE', 'MORES', 'GIRTH', 'SLIMY', 'AIDES', 'SPASM', 'BURRS', 'ALIBI', 'LYMPH', 'SAUCY', 'MUGGY', 'LITER', 'JOKED', 'GOOFY', 'EXAMS', 'ENACT', 'STORK', 'LURED', 'TOXIC', 'OMENS', 'NEARS',
'COVET', 'WRUNG', 'FORUM', 'VENOM', 'MOODY', 'ALDER', 'SASSY', 'FLAIR', 'GUILD', 'PRAYS', 'WRENS', 'HAULS', 'STAVE', 'TILTS', 'PECKS', 'STOMP', 'GALES', 'TEMPT', 'CAPES', 'MESAS', 'OMITS', 'TEPEE', 'HARRY', 'WRING', 'EVOKE', 'LIMES', 'CLUCK', 'LUNGE', 'HIGHS',
'CANES', 'GIDDY', 'LITHE', 'VERGE', 'KHAKI', 'QUEUE', 'LOATH', 'FOYER', 'OUTDO', 'FARED', 'DETER', 'CRUMB', 'ASTIR', 'SPIRE', 'JUMPY', 'EXTOL', 'BUOYS', 'STUBS', 'LUCID', 'THONG', 'AFORE', 'WHIFF', 'MAXIM', 'HULLS', 'CLOGS', 'SLATS', 'JIFFY', 'ARBOR', 'CINCH',
'IGLOO', 'GOODY', 'GAZES', 'DOWEL', 'CALMS', 'BITCH', 'SCOWL', 'GULPS', 'CODED', 'WAVER', 'MASON', 'LOBES', 'EBONY', 'FLAIL', 'ISLES', 'CLODS', 'DAZED', 'ADEPT', 'OOZED', 'SEDAN', 'CLAYS', 'WARTS', 'KETCH', 'SKUNK', 'MANES', 'ADORE', 'SNEER', 'MANGO', 'FIORD',
'FLORA', 'ROOMY', 'MINKS', 'THAWS', 'WATTS', 'FREER', 'EXULT', 'PLUSH', 'PALED', 'TWAIN', 'CLINK', 'SCAMP', 'PAWED', 'GROPE', 'BRAVO', 'GABLE', 'STINK', 'SEVER', 'WANED', 'RARER', 'REGAL', 'WARDS', 'FAWNS', 'BABES', 'UNIFY', 'AMEND', 'OAKEN', 'GLADE', 'VISOR',
'HEFTY', 'NINES', 'THROB', 'PECAN', 'BUTTS', 'PENCE', 'SILLS', 'JAILS', 'FLYER', 'SABER', 'NOMAD', 'MITER', 'BEEPS', 'DOMED', 'GULFS', 'CURBS', 'HEATH', 'MOORS', 'AORTA', 'LARKS', 'TANGY', 'WRYLY', 'CHEEP', 'RAGES', 'EVADE', 'LURES', 'FREAK', 'VOGUE', 'TUNIC',
'SLAMS', 'KNITS', 'DUMPY', 'MANIA', 'SPITS', 'FIRTH', 'HIKES', 'TROTS', 'NOSED', 'CLANK', 'DOGMA', 'BLOAT', 'BALSA', 'GRAFT', 'MIDDY', 'STILE', 'KEYED', 'FINCH', 'SPERM', 'CHAFF', 'WILES', 'AMIGO', 'COPRA', 'AMISS', 'EYING', 'TWIRL', 'LURCH', 'POPES', 'CHINS',
'SMOCK', 'TINES', 'GUISE', 'GRITS', 'JUNKS', 'SHOAL', 'CACHE', 'TAPIR', 'ATOLL', 'DEITY', 'TOILS', 'SPREE', 'MOCKS', 'SCANS', 'SHORN', 'REVEL', 'RAVEN', 'HOARY', 'REELS', 'SCUFF', 'MIMIC', 'WEEDY', 'CORNY', 'TRUER', 'ROUGE', 'EMBER', 'FLOES', 'TORSO', 'WIPES',
'EDICT', 'SULKY', 'RECUR', 'GROIN', 'BASTE', 'KINKS', 'SURER', 'PIGGY', 'MOLDY', 'FRANC', 'LIARS', 'INEPT', 'GUSTY', 'FACET', 'JETTY', 'EQUIP', 'LEPER', 'SLINK', 'SOARS', 'CATER', 'DOWRY', 'SIDED', 'YEARN', 'DECOY', 'TABOO', 'OVALS', 'HEALS', 'PLEAS', 'BERET',
'SPILT', 'GAYLY', 'ROVER', 'ENDOW', 'PYGMY', 'CARAT', 'ABBEY', 'VENTS', 'WAKEN', 'CHIMP', 'FUMED', 'SODAS', 'VINYL', 'CLOUT', 'WADES', 'MITES', 'SMIRK', 'BORES', 'BUNNY', 'SURLY', 'FROCK', 'FORAY', 'PURER', 'MILKS', 'QUERY', 'MIRED', 'BLARE', 'FROTH', 'GRUEL',
'NAVEL', 'PALER', 'PUFFY', 'CASKS', 'GRIME', 'DERBY', 'MAMMA', 'GAVEL', 'TEDDY', 'VOMIT', 'MOANS', 'ALLOT', 'DEFER', 'WIELD', 'VIPER', 'LOUSE', 'ERRED', 'HEWED', 'ABHOR', 'WREST', 'WAXEN', 'ADAGE', 'ARDOR', 'STABS', 'PORED', 'RONDO', 'LOPED', 'FISHY', 'BIBLE',
'HIRES', 'FOALS', 'FEUDS', 'JAMBS', 'THUDS', 'JEERS', 'KNEAD', 'QUIRK', 'RUGBY', 'EXPEL', 'GREYS', 'RIGOR', 'ESTER', 'LYRES', 'ABACK', 'GLUES', 'LOTUS', 'LURID', 'RUNGS', 'HUTCH', 'THYME', 'VALET', 'TOMMY', 'YOKES', 'EPICS', 'TRILL', 'PIKES', 'OZONE', 'CAPER',
'CHIME', 'FREES', 'FAMED', 'LEECH', 'SMITE', 'NEIGH', 'ERODE', 'ROBED', 'HOARD', 'SALVE', 'CONIC', 'GAWKY', 'CRAZE', 'JACKS', 'GLOAT', 'MUSHY', 'RUMPS', 'FETUS', 'WINCE', 'PINKS', 'SHALT', 'TOOTS', 'GLENS', 'COOED', 'RUSTS', 'STEWS', 'SHRED', 'PARKA', 'CHUGS',
'WINKS', 'CLOTS', 'SHREW', 'BOOED', 'FILMY', 'JUROR', 'DENTS', 'GUMMY', 'GRAYS', 'HOOKY', 'BUTTE', 'DOGIE', 'POLED', 'REAMS', 'FIFES', 'SPANK', 'GAYER', 'TEPID', 'SPOOK', 'TAINT', 'FLIRT', 'ROGUE', 'SPIKY', 'OPALS', 'MISER', 'COCKY', 'COYLY', 'BALMY', 'SLOSH',
'BRAWL', 'APHID', 'FAKED', 'HYDRA', 'BRAGS', 'CHIDE', 'YANKS', 'ALLAY', 'VIDEO', 'ALTOS', 'EASES', 'METED', 'CHASM', 'LONGS', 'EXCEL', 'TAFFY', 'IMPEL', 'SAVOR', 'KOALA', 'QUAYS', 'DAWNS', 'PROXY', 'CLOVE', 'DUETS', 'DREGS', 'TARDY', 'BRIAR', 'GRIMY', 'ULTRA',
'MEATY', 'HALVE', 'WAILS', 'SUEDE', 'MAUVE', 'ENVOY', 'ARSON', 'COVES', 'GOOEY', 'BREWS', 'SOFAS', 'CHUMS', 'AMAZE', 'ZOOMS', 'ABBOT', 'HALOS', 'SCOUR', 'SUING', 'CRIBS', 'SAGAS', 'ENEMA', 'WORDY', 'HARPS', 'COUPE', 'MOLAR', 'FLOPS', 'WEEPS', 'MINTS', 'ASHEN',
'FELTS', 'ASKEW', 'MUNCH', 'MEWED', 'DIVAN', 'VICES', 'JUMBO', 'BLOBS', 'BLOTS', 'SPUNK', 'ACRID', 'TOPAZ', 'CUBED', 'CLANS', 'FLEES', 'SLURS', 'GNAWS', 'WELDS', 'FORDS', 'EMITS', 'AGATE', 'PUMAS', 'MENDS', 'DARKS', 'DUKES', 'PLIES', 'CANNY', 'HOOTS', 'OOZES',
'LAMED', 'FOULS', 'CLEFS', 'NICKS', 'MATED', 'SKIMS', 'BRUNT', 'TUBER', 'TINGE', 'FATES', 'DITTY', 'THINS', 'FRETS', 'EIDER', 'BAYOU', 'MULCH', 'FASTS', 'AMASS', 'DAMPS', 'MORNS', 'FRIAR', 'PALSY', 'VISTA', 'CROON', 'CONCH', 'UDDER', 'TACOS', 'SKITS', 'MIKES',
'QUITS', 'PREEN', 'ASTER', 'ADDER', 'ELEGY', 'PULPY', 'SCOWS', 'BALED', 'HOVEL', 'LAVAS', 'CRAVE', 'OPTIC', 'WELTS', 'BUSTS', 'KNAVE', 'RAZED', 'SHINS', 'TOTES', 'SCOOT', 'DEARS', 'CROCK', 'MUTES', 'TRIMS', 'SKEIN', 'DOTED', 'SHUNS', 'VEERS', 'FAKES', 'YOKED',
'WOOED', 'HACKS', 'SPRIG', 'WANDS', 'LULLS', 'SEERS', 'SNOBS', 'NOOKS', 'PINED', 'PERKY', 'MOOED', 'FRILL', 'DINES', 'BOOZE', 'TRIPE', 'PRONG', 'DRIPS', 'ODDER', 'LEVEE', 'ANTIC', 'SIDLE', 'PITHY', 'CORKS', 'YELPS', 'JOKER', 'FLECK', 'BUFFS', 'SCRAM', 'TIERS',
'BOGEY', 'DOLED', 'IRATE', 'VALES', 'COPED', 'HAILS', 'ELUDE', 'BULKS', 'AIRED', 'VYING', 'STAGS', 'STREW', 'COCCI', 'PACTS', 'SCABS', 'SILOS', 'DUSTS', 'YODEL', 'TERSE', 'JADED', 'BASER', 'JIBES', 'FOILS', 'SWAYS', 'FORGO', 'SLAYS', 'PREYS', 'TREKS', 'QUELL',
'PEEKS', 'ASSAY', 'LURKS', 'EJECT', 'BOARS', 'TRITE', 'BELCH', 'GNASH', 'WANES', 'LUTES', 'WHIMS', 'DOSED', 'CHEWY', 'SNIPE', 'UMBRA', 'TEEMS', 'DOZES', 'KELPS', 'UPPED', 'BRAWN', 'DOPED', 'SHUSH', 'RINDS', 'SLUSH', 'MORON', 'VOILE', 'WOKEN', 'FJORD', 'SHEIK',
'JESTS', 'KAYAK', 'SLEWS', 'TOTED', 'SANER', 'DRAPE', 'PATTY', 'RAVES', 'SULFA', 'GRIST', 'SKIED', 'VIXEN', 'CIVET', 'VOUCH', 'TIARA', 'HOMEY', 'MOPED', 'RUNTS', 'SERGE', 'KINKY', 'RILLS', 'CORNS', 'BRATS', 'PRIES', 'AMBLE', 'FRIES', 'LOONS', 'TSARS', 'DATUM',
'MUSKY', 'PIGMY', 'GNOME', 'RAVEL', 'OVULE', 'ICILY', 'LIKEN', 'LEMUR', 'FRAYS', 'SILTS', 'SIFTS', 'PLODS', 'RAMPS', 'TRESS', 'EARLS', 'DUDES', 'WAIVE', 'KARAT', 'JOLTS', 'PEONS', 'BEERS', 'HORNY', 'PALES', 'WREAK', 'LAIRS', 'LYNCH', 'STANK', 'SWOON', 'IDLER',
'ABORT', 'BLITZ', 'ENSUE', 'ATONE', 'BINGO', 'ROVES', 'KILTS', 'SCALD', 'ADIOS', 'CYNIC', 'DULLS', 'MEMOS', 'ELFIN', 'DALES', 'PEELS', 'PEALS', 'BARES', 'SINUS', 'CRONE', 'SABLE', 'HINDS', 'SHIRK', 'ENROL', 'WILTS', 'ROAMS', 'DUPED', 'CYSTS', 'MITTS', 'SAFES',
'SPATS', 'COOPS', 'FILET', 'KNELL', 'REFIT', 'COVEY', 'PUNKS', 'KILNS', 'FITLY', 'ABATE', 'TALCS', 'HEEDS', 'DUELS', 'WANLY', 'RUFFS', 'GAUSS', 'LAPEL', 'JAUNT', 'WHELP', 'CLEAT', 'GAUZY', 'DIRGE', 'EDITS', 'WORMY', 'MOATS', 'SMEAR', 'PRODS', 'BOWEL', 'FRISK',
'VESTS', 'BAYED', 'RASPS', 'TAMES', 'DELVE', 'EMBED', 'BEFIT', 'WAFER', 'CEDED', 'NOVAS', 'FEIGN', 'SPEWS', 'LARCH', 'HUFFS', 'DOLES', 'MAMAS', 'HULKS', 'PRIED', 'BRIMS', 'IRKED', 'ASPIC', 'SWIPE', 'MEALY', 'SKIMP', 'BLUER', 'SLAKE', 'DOWDY', 'PENIS', 'BRAYS',
'PUPAS', 'EGRET', 'FLUNK', 'PHLOX', 'GRIPE', 'PEONY', 'DOUSE', 'BLURS', 'DARNS', 'SLUNK', 'LEFTS', 'CHATS', 'INANE', 'VIALS', 'STILT', 'RINKS', 'WOOFS', 'WOWED', 'BONGS', 'FROND', 'INGOT', 'EVICT', 'SINGE', 'SHYER', 'FLIED', 'SLOPS', 'DOLTS', 'DROOL', 'DELLS',
'WHELK', 'HIPPY', 'FETED', 'ETHER', 'COCOS', 'HIVES', 'JIBED', 'MAZES', 'TRIOS', 'SIRUP', 'SQUAB', 'LATHS', 'LEERS', 'PASTA', 'RIFTS', 'LOPES', 'ALIAS', 'WHIRS', 'DICED', 'SLAGS', 'LODES', 'FOXED', 'IDLED', 'PROWS', 'PLAIT', 'MALTS', 'CHAFE', 'COWER', 'TOYED',
'CHEFS', 'KEELS', 'STIES', 'RACER', 'ETUDE', 'SUCKS', 'SULKS', 'MICAS', 'CZARS', 'COPSE', 'AILED', 'ABLER', 'RABID', 'GOLDS', 'CROUP', 'SNAKY', 'VISAS', 'DRUNK', 'RESTS', 'CHILL', 'SLAIN', 'PANIC', 'CORDS', 'TUNED', 'CRISP', 'LEDGE', 'DIVED', 'SWAMP', 'CLUNG',
'STOLE', 'MOLDS', 'YARNS', 'LIVER', 'GAUGE', 'BREED', 'STOOL', 'GULLS', 'AWOKE', 'GROSS', 'DIARY', 'RAILS', 'BELLY', 'TREND', 'FLASK', 'STAKE', 'FRIED', 'DRAWS', 'ACTOR', 'HANDY', 'BOWLS', 'HASTE', 'SCOPE', 'DEALS', 'KNOTS', 'MOONS', 'ESSAY', 'THUMP', 'HANGS',
'BLISS', 'DEALT', 'GAINS', 'BOMBS', 'CLOWN', 'PALMS', 'CONES', 'ROAST', 'TIDAL', 'BORED', 'CHANT', 'ACIDS', 'DOUGH', 'CAMPS', 'SWORE', 'LOVER', 'HOOKS', 'MALES', 'COCOA', 'PUNCH', 'AWARD', 'REINS', 'NINTH', 'NOSES', 'LINKS', 'DRAIN', 'FILLS', 'NYLON', 'LUNAR',
'PULSE', 'FLOWN', 'ELBOW', 'FATAL', 'SITES', 'MOTHS', 'MEATS', 'FOXES', 'MINED', 'ATTIC', 'FIERY', 'MOUNT', 'USAGE', 'SWEAR', 'SNOWY', 'RUSTY', 'SCARE', 'TRAPS', 'RELAX', 'REACT', 'VALID', 'ROBIN', 'CEASE', 'GILLS', 'PRIOR', 'SAFER', 'POLIO', 'LOYAL', 'SWELL',
'SALTY', 'MARSH', 'VAGUE', 'WEAVE', 'MOUND', 'SEALS', 'MULES', 'VIRUS', 'SCOUT', 'ACUTE', 'WINDY', 'STOUT', 'FOLDS', 'SEIZE', 'HILLY', 'JOINS', 'PLUCK', 'STACK', 'LORDS', 'DUNES', 'BURRO', 'HAWKS', 'TROUT', 'FEEDS', 'SCARF', 'HALLS', 'COALS', 'TOWEL', 'SOULS',
'ELECT', 'BUGGY', 'PUMPS', 'LOANS', 'SPINS', 'FILES', 'OXIDE', 'PAINS', 'PHOTO', 'RIVAL', 'FLATS', 'SYRUP', 'RODEO', 'SANDS', 'MOOSE', 'PINTS', 'CURLY', 'COMIC', 'CLOAK', 'ONION', 'CLAMS', 'SCRAP', 'DIDST', 'COUCH', 'CODES', 'FAILS', 'OUNCE', 'LODGE', 'GREET',
'GYPSY', 'UTTER', 'PAVED', 'ZONES', 'FOURS', 'ALLEY', 'TILES', 'BLESS', 'CREST', 'ELDER', 'KILLS', 'YEAST', 'ERECT', 'BUGLE', 'MEDAL', 'ROLES', 'HOUND', 'SNAIL', 'ALTER', 'ANKLE', 'RELAY', 'LOOPS', 'ZEROS', 'BITES', 'MODES', 'DEBTS', 'REALM', 'GLOVE', 'RAYON',
'SWIMS', 'POKED', 'STRAY', 'LIFTS', 'MAKER', 'LUMPS', 'GRAZE', 'DREAD', 'BARNS', 'DOCKS', 'MASTS', 'POURS', 'WHARF', 'CURSE', 'PLUMP', 'ROBES', 'SEEKS', 'CEDAR', 'CURLS', 'JOLLY', 'MYTHS', 'CAGES', 'GLOOM', 'LOCKS', 'PEDAL', 'BEETS', 'CROWS', 'ANODE', 'SLASH',
'CREEP', 'ROWED', 'CHIPS', 'FISTS', 'WINES', 'CARES', 'VALVE', 'NEWER', 'MOTEL', 'IVORY', 'NECKS', 'CLAMP', 'BARGE', 'BLUES', 'ALIEN', 'FROWN', 'STRAP', 'CREWS', 'SHACK', 'GONNA', 'SAVES', 'STUMP', 'FERRY', 'IDOLS', 'COOKS', 'JUICY', 'GLARE', 'CARTS', 'ALLOY',
'BULBS', 'LAWNS', 'LASTS', 'FUELS', 'ODDLY', 'CRANE', 'FILED', 'WEIRD', 'SHAWL', 'SLIPS', 'TROOP', 'BOLTS', 'SUITE', 'SLEEK', 'QUILT', 'TRAMP', 'BLAZE', 'ATLAS', 'ODORS', 'SCRUB', 'CRABS', 'PROBE', 'LOGIC', 'ADOBE', 'EXILE', 'REBEL', 'GRIND', 'STING', 'SPINE',
'CLING', 'DESKS', 'GROVE', 'LEAPS', 'PROSE', 'LOFTY', 'AGONY', 'SNARE', 'TUSKS', 'BULLS', 'MOODS', 'HUMID', 'FINER', 'DIMLY', 'PLANK', 'CHINA', 'PINES', 'GUILT', 'SACKS', 'BRACE', 'QUOTE', 'LATHE', 'GAILY', 'FONTS', 'SCALP', 'ADOPT', 'FOGGY', 'FERNS', 'GRAMS',
'CLUMP', 'PERCH', 'TUMOR', 'TEENS', 'CRANK', 'FABLE', 'HEDGE', 'GENES', 'SOBER', 'BOAST', 'TRACT', 'CIGAR', 'UNITE', 'OWING', 'THIGH', 'HAIKU', 'SWISH', 'DIKES', 'WEDGE', 'BOOTH', 'EASED', 'FRAIL', 'COUGH', 'TOMBS', 'DARTS', 'FORTS', 'CHOIR', 'POUCH', 'PINCH',
'HAIRY', 'BUYER', 'TORCH', 'VIGOR', 'WALTZ', 'HEATS', 'HERBS', 'USERS', 'FLINT', 'CLICK', 'MADAM', 'BLEAK', 'BLUNT', 'AIDED', 'LACKS', 'MASKS', 'WADED', 'RISKS', 'NURSE', 'CHAOS', 'SEWED', 'CURED', 'AMPLE', 'LEASE', 'STEAK', 'SINKS', 'MERIT', 'BLUFF', 'BATHE',
'GLEAM', 'BONUS', 'COLTS', 'SHEAR', 'GLAND', 'SILKY', 'SKATE', 'BIRCH', 'ANVIL', 'SLEDS', 'GROAN', 'MAIDS', 'MEETS', 'SPECK', 'HYMNS', 'HINTS', 'DROWN', 'BOSOM', 'SLICK', 'QUEST', 'COILS', 'SPIED', 'SNOWS', 'STEAD', 'SNACK', 'PLOWS', 'BLOND', 'TAMED', 'THORN',
'WAITS', 'GLUED', 'BANJO', 'TEASE', 'ARENA', 'BULKY', 'CARVE', 'STUNT', 'WARMS', 'SHADY', 'RAZOR', 'FOLLY', 'LEAFY', 'NOTCH', 'FOOLS', 'OTTER', 'PEARS', 'FLUSH', 'GENUS', 'ACHED', 'FIVES', 'FLAPS', 'SPOUT', 'SMOTE', 'FUMES', 'ADAPT', 'CUFFS', 'TASTY', 'STOOP',
'CLIPS', 'DISKS', 'SNIFF', 'LANES', 'BRISK', 'IMPLY', 'DEMON', 'SUPER', 'FURRY', 'RAGED', 'GROWL', 'TEXTS', 'HARDY', 'STUNG', 'TYPED', 'HATES', 'WISER', 'TIMID', 'SERUM', 'BEAKS', 'ROTOR', 'CASTS', 'BATHS', 'GLIDE', 'PLOTS', 'TRAIT', 'RESIN', 'SLUMS', 'LYRIC',
'PUFFS', 'DECKS', 'BROOD', 'MOURN', 'ALOFT', 'ABUSE', 'WHIRL', 'EDGED', 'OVARY', 'QUACK', 'HEAPS', 'SLANG', 'AWAIT', 'CIVIC', 'SAINT', 'BEVEL', 'SONAR', 'AUNTS', 'PACKS', 'FROZE', 'TONIC', 'CORPS', 'SWARM', 'FRANK', 'REPAY', 'GAUNT', 'WIRED', 'NIECE', 'CELLO',
'NEEDY', 'CHUCK', 'STONY', 'MEDIA', 'SURGE', 'HURTS', 'REPEL', 'HUSKY', 'DATED', 'HUNTS', 'MISTS', 'EXERT', 'DRIES', 'MATES', 'SWORN', 'BAKER', 'SPICE', 'OASIS', 'BOILS', 'SPURS', 'DOVES', 'SNEAK', 'PACES', 'COLON', 'SIEGE', 'STRUM', 'DRIER', 'CACAO', 'HUMUS',
'BALES', 'PIPED', 'NASTY', 'RINSE', 'BOXER', 'SHRUB', 'AMUSE', 'TACKS', 'CITED', 'SLUNG', 'DELTA', 'LADEN', 'LARVA', 'RENTS', 'YELLS', 'SPOOL', 'SPILL', 'CRUSH', 'JEWEL', 'SNAPS', 'STAIN', 'KICKS', 'TYING', 'SLITS', 'RATED', 'EERIE', 'SMASH', 'PLUMS', 'ZEBRA',
'EARNS', 'BUSHY', 'SCARY', 'SQUAD', 'TUTOR', 'SILKS', 'SLABS', 'BUMPS', 'EVILS', 'FANGS', 'SNOUT', 'PERIL', 'PIVOT', 'YACHT', 'LOBBY', 'JEANS', 'GRINS', 'VIOLA', 'LINER', 'COMET', 'SCARS', 'CHOPS', 'RAIDS', 'EATER', 'SLATE', 'SKIPS', 'SOLES', 'MISTY', 'URINE',
'KNOBS', 'SLEET', 'HOLLY', 'PESTS', 'FORKS', 'GRILL', 'TRAYS', 'PAILS', 'BORNE', 'TENOR', 'WARES', 'CAROL', 'WOODY', 'CANON', 'WAKES', 'KITTY', 'MINER', 'POLLS', 'SHAKY', 'NASAL', 'SCORN', 'CHESS', 'TAXIS', 'CRATE', 'SHYLY', 'TULIP', 'FORGE', 'NYMPH', 'BUDGE',
'LOWLY', 'ABIDE', 'DEPOT', 'OASES', 'ASSES', 'SHEDS', 'FUDGE', 'PILLS', 'RIVET', 'THINE', 'GROOM', 'LANKY', 'BOOST', 'BROTH', 'HEAVE', 'GRAVY', 'BEECH', 'TIMED', 'QUAIL', 'INERT', 'GEARS', 'CHICK', 'HINGE', 'TRASH', 'CLASH', 'SIGHS', 'RENEW', 'BOUGH', 'DWARF',
'SLOWS', 'QUILL', 'SHAVE', 'SPORE', 'SIXES', 'CHUNK', 'MADLY', 'PACED', 'BRAID', 'FUZZY', 'MOTTO', 'SPIES', 'SLACK', 'MUCUS', 'MAGMA', 'AWFUL', 'DISCS', 'ERASE', 'POSED', 'ASSET', 'CIDER', 'TAPER', 'THEFT', 'CHURN', 'SATIN', 'SLOTS', 'TAXED', 'BULLY', 'SLOTH',
'SHALE', 'TREAD', 'RAKED', 'CURDS', 'MANOR', 'AISLE', 'BULGE', 'LOINS', 'STAIR', 'TAPES', 'LEANS', 'BUNKS', 'SQUAT', 'TOWED', 'LANCE', 'PANES', 'SAKES', 'HEIRS', 'CASTE', 'DUMMY', 'PORES', 'FAUNA', 'CROOK', 'POISE', 'EPOCH', 'RISKY', 'WARNS', 'FLING', 'BERRY',
'GRAPE', 'FLANK', 'DRAGS', 'SQUID', 'PELTS', 'ICING', 'IRONY', 'IRONS', 'BARKS', 'WHOOP', 'CHOKE', 'DIETS', 'WHIPS', 'TALLY', 'DOZED', 'TWINE', 'KITES', 'BIKES', 'TICKS', 'RIOTS', 'ROARS', 'VAULT', 'LOOMS', 'SCOLD', 'BLINK', 'DANDY', 'PUPAE', 'SIEVE', 'SPIKE',
'DUCTS', 'LENDS', 'PIZZA', 'BRINK', 'WIDEN', 'PLUMB', 'PAGAN', 'FEATS', 'BISON', 'SOGGY', 'SCOOP', 'ARGON', 'NUDGE', 'SKIFF', 'AMBER', 'SEXES', 'ROUSE', 'SALTS', 'HITCH', 'EXALT', 'LEASH', 'DINED', 'CHUTE', 'SNORT', 'GUSTS', 'MELON', 'CHEAT', 'REEFS', 'LLAMA',
'LASSO', 'DEBUT', 'QUOTA', 'OATHS', 'PRONE', 'MIXES', 'RAFTS', 'DIVES', 'STALE', 'INLET', 'FLICK', 'PINTO', 'BROWS', 'UNTIE', 'BATCH', 'GREED', 'CHORE', 'STIRS', 'BLUSH', 'ONSET', 'BARBS', 'VOLTS', 'BEIGE', 'SWOOP', 'PADDY', 'LACED', 'SHOVE', 'JERKY', 'POPPY',
'LEAKS', 'FARES', 'DODGE', 'GODLY', 'SQUAW', 'AFFIX', 'BRUTE', 'NICER', 'UNDUE', 'SNARL', 'MERGE', 'DOSES', 'SHOWY', 'DADDY', 'ROOST', 'VASES', 'SWIRL', 'PETTY', 'COLDS', 'CURRY', 'COBRA', 'GENIE', 'FLARE', 'MESSY', 'CORES', 'SOAKS', 'RIPEN', 'WHINE', 'AMINO',
'PLAID', 'SPINY', 'MOWED', 'BATON', 'PEERS', 'VOWED', 'PIOUS', 'SWANS', 'EXITS', 'AFOOT', 'PLUGS', 'IDIOM', 'CHILI', 'RITES', 'SERFS', 'CLEFT', 'BERTH', 'GRUBS', 'ANNEX', 'DIZZY', 'HASTY', 'LATCH', 'WASPS', 'MIRTH', 'BARON', 'PLEAD', 'ALOOF', 'AGING', 'PIXEL',
'BARED', 'MUMMY', 'HOTLY', 'AUGER', 'BUDDY', 'CHAPS', 'BADGE', 'STARK', 'FAIRS', 'GULLY', 'MUMPS', 'EMERY', 'FILLY', 'OVENS', 'DRONE', 'GAUZE', 'IDIOT', 'FUSSY', 'ANNOY', 'SHANK', 'GOUGE', 'BLEED', 'ELVES', 'ROPED', 'UNFIT', 'BAGGY', 'MOWER', 'SCANT', 'GRABS',
'FLEAS', 'LOUSY', 'ALBUM', 'SAWED', 'COOKY', 'MURKY', 'INFER', 'BURLY', 'WAGED', 'DINGY', 'BRINE', 'KNEEL', 'CREAK', 'VANES', 'SMOKY', 'SPURT', 'COMBS', 'EASEL', 'LACES', 'HUMPS', 'RUMOR', 'AROMA', 'HORDE', 'SWISS', 'LEAPT', 'OPIUM', 'SLIME', 'AFIRE', 'PANSY',
'MARES', 'SOAPS', 'HUSKS', 'SNIPS', 'HAZEL', 'LINED', 'CAFES', 'NAIVE', 'WRAPS', 'SIZED', 'PIERS', 'BESET', 'AGILE', 'TONGS', 'STEED', 'FRAUD', 'BOOTY', 'VALOR', 'DOWNY', 'WITTY', 'MOSSY', 'PSALM', 'SCUBA', 'TOURS', 'POLKA', 'MILKY', 'GAUDY', 'SHRUG', 'TUFTS',
'WILDS', 'LASER', 'TRUSS', 'HARES', 'CREED', 'LILAC', 'SIREN', 'TARRY', 'BRIBE', 'SWINE', 'MUTED', 'FLIPS', 'CURES', 'SINEW', 'BOXED', 'HOOPS', 'GASPS', 'HOODS', 'NICHE', 'YUCCA', 'GLOWS', 'SEWER', 'WHACK', 'FUSES', 'GOWNS', 'DROOP', 'BUCKS', 'PANGS', 'MAILS',
'WHISK', 'HAVEN', 'CLASP', 'SLING', 'STINT', 'URGES', 'CHAMP', 'PIETY', 'CHIRP', 'PLEAT', 'POSSE', 'SUNUP', 'MENUS', 'HOWLS', 'QUAKE', 'KNACK', 'PLAZA', 'FIEND', 'CAKED', 'BANGS', 'ERUPT', 'POKER', 'OLDEN', 'CRAMP', 'VOTER', 'POSES', 'MANLY', 'SLUMP', 'FINED',
'GRIPS', 'GAPED', 'PURGE', 'HIKED', 'MAIZE', 'FLUFF', 'STRUT', 'SLOOP', 'PROWL', 'ROACH', 'COCKS', 'BLAND', 'DIALS', 'PLUME', 'SLAPS', 'SOUPS', 'DULLY', 'WILLS', 'FOAMS', 'SOLOS', 'SKIER', 'EAVES', 'TOTEM', 'FUSED', 'LATEX', 'VEILS', 'MUSED', 'MAINS', 'MYRRH',
'RACKS', 'GALLS','WHICH', 'THERE', 'THEIR', 'ABOUT', 'WOULD', 'THESE', 'OTHER', 'WORDS', 'COULD', 'WRITE', 'FIRST', 'WATER', 'AFTER', 'WHERE', 'RIGHT', 'THINK', 'THREE', 'YEARS', 'PLACE', 'SOUND', 'GREAT', 'AGAIN', 'STILL', 'EVERY', 'SMALL', 'FOUND', 'THOSE',
'NEVER', 'UNDER', 'MIGHT', 'WHILE', 'HOUSE', 'WORLD', 'BELOW', 'ASKED', 'GOING', 'LARGE', 'UNTIL', 'ALONG', 'SHALL', 'BEING', 'OFTEN', 'EARTH', 'BEGAN', 'SINCE', 'STUDY', 'NIGHT', 'LIGHT', 'ABOVE', 'PAPER', 'PARTS', 'YOUNG', 'STORY', 'POINT', 'TIMES', 'HEARD',
'WHOLE', 'WHITE', 'GIVEN', 'MEANS', 'MUSIC', 'MILES', 'THING', 'TODAY', 'LATER', 'USING', 'MONEY', 'LINES', 'ORDER', 'GROUP', 'AMONG', 'LEARN', 'KNOWN', 'SPACE', 'TABLE', 'EARLY', 'TREES', 'SHORT', 'HANDS', 'STATE', 'BLACK', 'SHOWN', 'STOOD', 'FRONT', 'VOICE',
'KINDS', 'MAKES', 'COMES', 'CLOSE', 'POWER', 'LIVED', 'VOWEL', 'TAKEN', 'BUILT', 'HEART', 'READY', 'QUITE', 'CLASS', 'BRING', 'ROUND', 'HORSE', 'SHOWS', 'PIECE', 'GREEN', 'STAND', 'BIRDS', 'START', 'RIVER', 'TRIED', 'LEAST', 'FIELD', 'WHOSE', 'GIRLS', 'LEAVE',
'ADDED', 'COLOR', 'THIRD', 'HOURS', 'MOVED', 'PLANT', 'DOING', 'NAMES', 'FORMS', 'HEAVY', 'IDEAS', 'CRIED', 'CHECK', 'FLOOR', 'BEGIN', 'WOMAN', 'ALONE', 'PLANE', 'SPELL', 'WATCH', 'CARRY', 'WROTE', 'CLEAR', 'NAMED', 'BOOKS', 'CHILD', 'GLASS', 'HUMAN', 'TAKES',
'PARTY', 'BUILD', 'SEEMS', 'BLOOD', 'SIDES', 'SEVEN', 'MOUTH', 'SOLVE', 'NORTH', 'VALUE', 'DEATH', 'MAYBE', 'HAPPY', 'TELLS', 'GIVES', 'LOOKS', 'SHAPE', 'LIVES', 'STEPS', 'AREAS', 'SENSE', 'SPEAK', 'FORCE', 'OCEAN', 'SPEED', 'WOMEN', 'METAL', 'SOUTH', 'GRASS',
'SCALE', 'CELLS', 'LOWER', 'SLEEP', 'WRONG', 'PAGES', 'SHIPS', 'NEEDS', 'ROCKS', 'EIGHT', 'MAJOR', 'LEVEL', 'TOTAL', 'AHEAD', 'REACH', 'STARS', 'STORE', 'SIGHT', 'TERMS', 'CATCH', 'WORKS', 'BOARD', 'COVER', 'SONGS', 'EQUAL', 'STONE', 'WAVES', 'GUESS', 'DANCE',
'SPOKE', 'BREAK', 'CAUSE', 'RADIO', 'WEEKS', 'LANDS', 'BASIC', 'LIKED', 'TRADE', 'FRESH', 'FINAL', 'FIGHT', 'MEANT', 'DRIVE', 'SPENT', 'LOCAL', 'WAXES', 'KNOWS', 'TRAIN', 'BREAD', 'HOMES', 'TEETH', 'COAST', 'THICK', 'BROWN', 'CLEAN', 'QUIET', 'SUGAR', 'FACTS',
'STEEL', 'FORTH', 'RULES', 'NOTES', 'UNITS', 'PEACE', 'MONTH', 'VERBS', 'SEEDS', 'HELPS', 'SHARP', 'VISIT', 'WOODS', 'CHIEF', 'WALLS', 'CROSS', 'WINGS', 'GROWN', 'CASES', 'FOODS', 'CROPS', 'FRUIT', 'STICK', 'WANTS', 'STAGE', 'SHEEP', 'NOUNS', 'PLAIN', 'DRINK',
'BONES', 'APART', 'TURNS', 'MOVES', 'TOUCH', 'ANGLE', 'BASED', 'RANGE', 'MARKS', 'TIRED', 'OLDER', 'FARMS', 'SPEND', 'SHOES', 'GOODS', 'CHAIR', 'TWICE', 'CENTS', 'EMPTY', 'ALIKE', 'STYLE', 'BROKE', 'PAIRS', 'COUNT', 'ENJOY', 'SCORE', 'SHORE', 'ROOTS', 'PAINT',
'HEADS', 'SHOOK', 'SERVE', 'ANGRY', 'CROWD', 'WHEEL', 'QUICK', 'DRESS', 'SHARE', 'ALIVE', 'NOISE', 'SOLID', 'CLOTH', 'SIGNS', 'HILLS', 'TYPES', 'DRAWN', 'WORTH', 'TRUCK', 'PIANO', 'UPPER', 'LOVED', 'USUAL', 'FACES', 'DROVE', 'CABIN', 'BOATS', 'TOWNS', 'PROUD',
'COURT', 'MODEL', 'PRIME', 'FIFTY', 'PLANS', 'YARDS', 'PROVE', 'TOOLS', 'PRICE', 'SHEET', 'SMELL', 'BOXES', 'RAISE', 'MATCH', 'TRUTH', 'ROADS', 'THREW', 'ENEMY', 'LUNCH', 'CHART', 'SCENE', 'GRAPH', 'DOUBT', 'GUIDE', 'WINDS', 'BLOCK', 'GRAIN', 'SMOKE', 'MIXED',
'GAMES', 'WAGON', 'SWEET', 'TOPIC', 'EXTRA', 'PLATE', 'TITLE', 'KNIFE', 'FENCE', 'FALLS', 'CLOUD', 'WHEAT', 'PLAYS', 'ENTER', 'BROAD', 'STEAM', 'ATOMS', 'PRESS', 'LYING', 'BASIS', 'CLOCK', 'TASTE', 'GROWS', 'THANK', 'STORM', 'AGREE', 'BRAIN', 'TRACK', 'SMILE',
'FUNNY', 'BEACH', 'STOCK', 'HURRY', 'SAVED', 'SORRY', 'GIANT', 'TRAIL', 'OFFER', 'OUGHT', 'ROUGH', 'DAILY', 'AVOID', 'KEEPS', 'THROW', 'ALLOW', 'CREAM', 'LAUGH', 'EDGES', 'TEACH', 'FRAME', 'BELLS', 'DREAM', 'MAGIC', 'OCCUR', 'ENDED', 'CHORD', 'FALSE', 'SKILL',
'HOLES', 'DOZEN', 'BRAVE', 'APPLE', 'CLIMB', 'OUTER', 'PITCH', 'RULER', 'HOLDS', 'FIXED', 'COSTS', 'CALLS', 'BLANK', 'STAFF', 'LABOR', 'EATEN', 'YOUTH', 'TONES', 'HONOR', 'GLOBE', 'GASES', 'DOORS', 'POLES', 'LOOSE', 'APPLY', 'TEARS', 'EXACT', 'BRUSH', 'CHEST',
'LAYER', 'WHALE', 'MINOR', 'FAITH', 'TESTS', 'JUDGE', 'ITEMS', 'WORRY', 'WASTE', 'HOPED', 'STRIP', 'BEGUN', 'ASIDE', 'LAKES', 'BOUND', 'DEPTH', 'CANDY', 'EVENT', 'WORSE', 'AWARE', 'SHELL', 'ROOMS', 'RANCH', 'IMAGE', 'SNAKE', 'ALOUD', 'DRIED', 'LIKES', 'MOTOR',
'POUND', 'KNEES', 'REFER', 'FULLY', 'CHAIN', 'SHIRT', 'FLOUR', 'DROPS', 'SPITE', 'ORBIT', 'BANKS', 'SHOOT', 'CURVE', 'TRIBE', 'TIGHT', 'BLIND', 'SLEPT', 'SHADE', 'CLAIM', 'FLIES', 'THEME', 'QUEEN', 'FIFTH', 'UNION', 'HENCE', 'STRAW', 'ENTRY', 'ISSUE', 'BIRTH',
'FEELS', 'ANGER', 'BRIEF', 'RHYME', 'GLORY', 'GUARD', 'FLOWS', 'FLESH', 'OWNED', 'TRICK', 'YOURS', 'SIZES', 'NOTED', 'WIDTH', 'BURST', 'ROUTE', 'LUNGS', 'UNCLE', 'BEARS', 'ROYAL', 'KINGS', 'FORTY', 'TRIAL', 'CARDS', 'BRASS', 'OPERA', 'CHOSE', 'OWNER', 'VAPOR',
'BEATS', 'MOUSE', 'TOUGH', 'WIRES', 'METER', 'TOWER', 'FINDS', 'INNER', 'STUCK', 'ARROW', 'POEMS', 'LABEL', 'SWING', 'SOLAR', 'TRULY', 'TENSE', 'BEANS', 'SPLIT', 'RISES', 'WEIGH', 'HOTEL', 'STEMS', 'PRIDE', 'SWUNG', 'GRADE', 'DIGIT', 'BADLY', 'BOOTS', 'PILOT',
'SALES', 'SWEPT', 'LUCKY', 'PRIZE', 'STOVE', 'TUBES', 'ACRES', 'WOUND', 'STEEP', 'SLIDE', 'TRUNK', 'ERROR', 'PORCH', 'SLAVE', 'EXIST', 'FACED', 'MINES', 'MARRY', 'JUICE', 'RACED', 'WAVED', 'GOOSE', 'TRUST', 'FEWER', 'FAVOR', 'MILLS', 'VIEWS', 'JOINT', 'EAGER',
'SPOTS', 'BLEND', 'RINGS', 'ADULT', 'INDEX', 'NAILS', 'HORNS', 'BALLS', 'FLAME', 'RATES', 'DRILL', 'TRACE', 'SKINS', 'WAXED', 'SEATS', 'STUFF', 'RATIO', 'MINDS', 'DIRTY', 'SILLY', 'COINS', 'HELLO', 'TRIPS', 'LEADS', 'RIFLE', 'HOPES', 'BASES', 'SHINE', 'BENCH',
'MORAL', 'FIRES', 'MEALS', 'SHAKE', 'SHOPS', 'CYCLE', 'MOVIE', 'SLOPE', 'CANOE', 'TEAMS', 'FOLKS', 'FIRED', 'BANDS', 'THUMB', 'SHOUT', 'CANAL', 'HABIT', 'REPLY', 'RULED', 'FEVER', 'CRUST', 'SHELF', 'WALKS', 'MIDST', 'CRACK', 'PRINT', 'TALES', 'COACH', 'STIFF',
'FLOOD', 'VERSE', 'AWAKE', 'ROCKY', 'MARCH', 'FAULT', 'SWIFT', 'FAINT', 'CIVIL', 'GHOST', 'FEAST', 'BLADE', 'LIMIT', 'GERMS', 'READS', 'DUCKS', 'DAIRY', 'WORST', 'GIFTS', 'LISTS', 'STOPS', 'RAPID', 'BRICK', 'CLAWS', 'BEADS', 'BEAST', 'SKIRT', 'CAKES', 'LIONS',
'FROGS', 'TRIES', 'NERVE', 'GRAND', 'ARMED', 'TREAT', 'HONEY', 'MOIST', 'LEGAL', 'PENNY', 'CROWN', 'SHOCK', 'TAXES', 'SIXTY', 'ALTAR', 'PULLS', 'SPORT', 'DRUMS', 'TALKS', 'DYING', 'DATES', 'DRANK', 'BLOWS', 'LEVER', 'WAGES', 'PROOF', 'DRUGS', 'TANKS', 'SINGS',
'TAILS', 'PAUSE', 'HERDS', 'AROSE', 'HATED', 'CLUES', 'NOVEL', 'SHAME', 'BURNT', 'RACES', 'FLASH', 'WEARY', 'HEELS', 'TOKEN', 'COATS', 'SPARE', 'SHINY', 'ALARM', 'DIMES', 'SIXTH', 'CLERK', 'MERCY', 'SUNNY', 'GUEST', 'FLOAT', 'SHONE', 'PIPES', 'WORMS', 'BILLS',
'SWEAT', 'SUITS', 'SMART', 'UPSET', 'RAINS', 'SANDY', 'RAINY', 'PARKS', 'SADLY', 'FANCY', 'RIDER', 'UNITY', 'BUNCH', 'ROLLS', 'CRASH', 'CRAFT', 'NEWLY', 'GATES', 'HATCH', 'PATHS', 'FUNDS', 'WIDER', 'GRACE', 'GRAVE', 'TIDES', 'ADMIT', 'SHIFT', 'SAILS', 'PUPIL',
'TIGER', 'ANGEL', 'CRUEL', 'AGENT', 'DRAMA', 'URGED', 'PATCH', 'NESTS', 'VITAL', 'SWORD', 'BLAME', 'WEEDS', 'SCREW', 'VOCAL', 'BACON', 'CHALK', 'CARGO', 'CRAZY', 'ACTED', 'GOATS', 'ARISE', 'WITCH', 'LOVES', 'QUEER', 'DWELL', 'BACKS', 'ROPES', 'SHOTS', 'MERRY',
'PHONE', 'CHEEK', 'PEAKS', 'IDEAL', 'BEARD', 'EAGLE', 'CREEK', 'CRIES', 'ASHES', 'STALL', 'YIELD', 'MAYOR', 'OPENS', 'INPUT', 'FLEET', 'TOOTH', 'CUBIC', 'WIVES', 'BURNS', 'POETS', 'APRON', 'SPEAR', 'ORGAN', 'CLIFF', 'STAMP', 'PASTE', 'RURAL', 'BAKED', 'CHASE',
'SLICE', 'SLANT', 'KNOCK', 'NOISY', 'SORTS', 'STAYS', 'WIPED', 'BLOWN', 'PILED', 'CLUBS', 'CHEER', 'WIDOW', 'TWIST', 'TENTH', 'HIDES', 'COMMA', 'SWEEP', 'SPOON', 'STERN', 'CREPT', 'MAPLE', 'DEEDS', 'RIDES', 'MUDDY', 'CRIME', 'JELLY', 'RIDGE', 'DRIFT', 'DUSTY',
'DEVIL', 'TEMPO', 'HUMOR', 'SENDS', 'STEAL', 'TENTS', 'WAIST', 'ROSES', 'REIGN', 'NOBLE', 'CHEAP', 'DENSE', 'LINEN', 'GEESE', 'WOVEN', 'POSTS', 'HIRED', 'WRATH', 'SALAD', 'BOWED', 'TIRES', 'SHARK', 'BELTS', 'GRASP', 'BLAST', 'POLAR', 'FUNGI', 'TENDS', 'PEARL',
'LOADS', 'JOKES', 'VEINS', 'FROST', 'HEARS', 'LOSES', 'HOSTS', 'DIVER', 'PHASE', 'TOADS', 'ALERT', 'TASKS', 'SEAMS', 'CORAL', 'FOCUS', 'NAKED', 'PUPPY', 'JUMPS', 'SPOIL', 'QUART', 'MACRO', 'FEARS', 'FLUNG', 'SPARK', 'VIVID', 'BROOK', 'STEER', 'SPRAY', 'DECAY',
'PORTS', 'SOCKS', 'URBAN', 'GOALS', 'GRANT', 'MINUS', 'FILMS', 'TUNES', 'SHAFT', 'FIRMS', 'SKIES', 'BRIDE', 'WRECK', 'FLOCK', 'STARE', 'HOBBY', 'BONDS', 'DARED', 'FADED', 'THIEF', 'CRUDE', 'PANTS', 'FLUTE', 'VOTES', 'TONAL', 'RADAR', 'WELLS', 'SKULL', 'HAIRS',
'ARGUE', 'WEARS', 'DOLLS', 'VOTED', 'CAVES', 'CARED', 'BROOM', 'SCENT', 'PANEL', 'FAIRY', 'OLIVE', 'BENDS', 'PRISM', 'LAMPS', 'CABLE', 'PEACH', 'RUINS', 'RALLY', 'SCHWA', 'LAMBS', 'SELLS', 'COOLS', 'DRAFT', 'CHARM', 'LIMBS', 'BRAKE', 'GAZED', 'CUBES', 'DELAY',
'BEAMS', 'FETCH', 'RANKS', 'ARRAY', 'HARSH', 'CAMEL', 'VINES', 'PICKS', 'NAVAL', 'PURSE', 'RIGID', 'CRAWL', 'TOAST', 'SOILS', 'SAUCE', 'BASIN', 'PONDS', 'TWINS', 'WRIST', 'FLUID', 'POOLS', 'BRAND', 'STALK', 'ROBOT', 'REEDS', 'HOOFS', 'BUSES', 'SHEER', 'GRIEF',
'BLOOM', 'DWELT', 'MELTS', 'RISEN', 'FLAGS', 'KNELT', 'FIBER', 'ROOFS', 'FREED', 'ARMOR', 'PILES', 'AIMED', 'ALGAE', 'TWIGS', 'LEMON', 'DITCH']
    wordlist = {5: five_letters}.get(
        length(solution), five_letters)
    previous_guesses = game >> L[RT.Guess] | value | collect

    equal_to_length = length | equals[length(solution)]
    in_wordlist = contained_in[wordlist + [solution]]
    not_previous_guess = Not[contained_in[previous_guesses]]
    is_eligible_guess = And[equal_to_length][in_wordlist][not_previous_guess]

    if is_eligible_guess(guess):
        guess_result, discard_letters = make_guess(guess, solution)
        # If this is the last guess
        if len(previous_guesses) == MAX_GUESSES - 1:
            [
                (game, RT.Guess, guess),
                (completed <= True),
            ] | transact[g] | run
            return make_return(guess_result=guess_result, failed=True, discard_letters=discard_letters)
        else:
            [
                (game, RT.Guess, guess),
            ] | transact[g] | run
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
    # NOTE This is added here because fetching and parsing the wordlist with each request is costly and slow.
    five_letters = ['CASAS', 'WITHS', 'DODGY', 'SCUDI', 'MUNGS', 'MUONS', 'UREAS', 'IOCTL', 'UNHIP', 'KRONE', 'SAGER', 'VERST', 'EXPAT', 'GRONK', 'UVULA', 'SHAWM', 'BILGY', 'BRAES', 'CENTO', 'WEBBY', 'LIPPY', 'GAMIC', 'LORDY', 'MAZED', 'TINGS', 'SHOAT', 'FAERY', 'WIRER',
'DIAZO', 'CARER', 'RATER', 'GREPS', 'RENTE', 'ZLOTY', 'VIERS', 'UNAPT', 'POOPS', 'FECAL', 'KEPIS', 'TAXON', 'EYERS', 'WONTS', 'SPINA', 'STOAE', 'YENTA', 'POOEY', 'BURET', 'JAPAN', 'BEDEW', 'HAFTS', 'SELFS', 'OARED', 'HERBY', 'PRYER', 'OAKUM', 'DINKS', 'TITTY',
'SEPOY', 'PENES', 'FUSEE', 'WINEY', 'GIMPS', 'NIHIL', 'RILLE', 'GIBER', 'OUSEL', 'UMIAK', 'CUPPY', 'HAMES', 'SHITS', 'AZINE', 'GLADS', 'TACET', 'BUMPH', 'COYER', 'HONKY', 'GAMER', 'GOOKY', 'WASPY', 'SEDGY', 'BENTS', 'VARIA', 'DJINN', 'JUNCO', 'PUBIC', 'WILCO',
'LAZES', 'IDYLS', 'LUPUS', 'RIVES', 'SNOOD', 'SCHMO', 'SPAZZ', 'FINIS', 'NOTER', 'PAVAN', 'ORBED', 'BATES', 'PIPET', 'BADDY', 'GOERS', 'SHAKO', 'STETS', 'SEBUM', 'SEETH', 'LOBAR', 'RAVER', 'AJUGA', 'RICED', 'VELDS', 'DRIBS', 'VILLE', 'DHOWS', 'UNSEW', 'HALMA',
'KRONA', 'LIMBY', 'JIFFS', 'TREYS', 'BAUDS', 'PFFFT', 'MIMER', 'PLEBS', 'CANER', 'JIBER', 'CUPPA', 'WASHY', 'CHUFF', 'UNARM', 'YUKKY', 'STYES', 'WAKER', 'FLAKS', 'MACES', 'RIMES', 'GIMPY', 'GUANO', 'LIRAS', 'KAPOK', 'SCUDS', 'BWANA', 'ORING', 'AIDER', 'PRIER',
'KLUGY', 'MONTE', 'GOLEM', 'VELAR', 'FIRER', 'PIETA', 'UMBEL', 'CAMPO', 'UNPEG', 'FOVEA', 'ABEAM', 'BOSON', 'ASKER', 'GOTHS', 'VOCAB', 'VINED', 'TROWS', 'TIKIS', 'LOPER', 'INDIE', 'BOFFS', 'SPANG', 'GRAPY', 'TATER', 'ICHOR', 'KILTY', 'LOCHS', 'SUPES', 'DEGAS',
'FLICS', 'TORSI', 'BETHS', 'WEBER', 'RESAW', 'LAWNY', 'COVEN', 'MUJIK', 'RELET', 'THERM', 'HEIGH', 'SHNOR', 'TRUED', 'ZAYIN', 'LIEST', 'BARFS', 'BASSI', 'QOPHS', 'ROILY', 'FLABS', 'PUNNY', 'OKRAS', 'HANKS', 'DIPSO', 'NERFS', 'FAUNS', 'CALLA', 'PSEUD', 'LURER',
'MAGUS', 'OBEAH', 'ATRIA', 'TWINK', 'PALMY', 'POCKY', 'PENDS', 'RECTA', 'PLONK', 'SLAWS', 'KEENS', 'NICAD', 'PONES', 'INKER', 'WHEWS', 'GROKS', 'MOSTS', 'TREWS', 'ULNAR', 'GYPPY', 'COCAS', 'EXPOS', 'ERUCT', 'OILER', 'VACUA', 'DRECK', 'DATER', 'ARUMS', 'TUBAL',
'VOXEL', 'DIXIT', 'BEERY', 'ASSAI', 'LADES', 'ACTIN', 'GHOTI', 'BUZZY', 'MEADS', 'GRODY', 'RIBBY', 'CLEWS', 'CREME', 'EMAIL', 'PYXIE', 'KULAK', 'BOCCI', 'RIVED', 'DUDDY', 'HOPER', 'LAPIN', 'WONKS', 'PETRI', 'PHIAL', 'FUGAL', 'HOLON', 'BOOMY', 'DUOMO', 'MUSOS',
'SHIER', 'HAYER', 'PORGY', 'HIVED', 'LITHO', 'FISTY', 'STAGY', 'LUVYA', 'MARIA', 'SMOGS', 'ASANA', 'YOGIC', 'SLOMO', 'FAWNY', 'AMINE', 'WEFTS', 'GONAD', 'TWIRP', 'BRAVA', 'PLYER', 'FERMI', 'LOGES', 'NITER', 'REVET', 'UNATE', 'GYVED', 'TOTTY', 'ZAPPY', 'HONER',
'GIROS', 'DICER', 'CALKS', 'LUXES', 'MONAD', 'CRUFT', 'QUOIN', 'FUMER', 'AMPED', 'SHLEP', 'VINCA', 'YAHOO', 'VULVA', 'ZOOEY', 'DRYAD', 'NIXIE', 'MOPER', 'IAMBS', 'LUNES', 'NUDIE', 'LIMNS', 'WEALS', 'NOHOW', 'MIAOW', 'GOUTS', 'MYNAS', 'MAZER', 'KIKES', 'OXEYE',
'STOUP', 'JUJUS', 'DEBAR', 'PUBES', 'TAELS', 'DEFUN', 'RANDS', 'BLEAR', 'PAVER', 'GOOSY', 'SPROG', 'OLEOS', 'TOFFY', 'PAWER', 'MACED', 'CRITS', 'KLUGE', 'TUBED', 'SAHIB', 'GANEF', 'SCATS', 'SPUTA', 'VANED', 'ACNED', 'TAXOL', 'PLINK', 'OWETH', 'TRIBS', 'RESAY',
'BOULE', 'THOUS', 'HAPLY', 'GLANS', 'MAXIS', 'BEZEL', 'ANTIS', 'PORKS', 'QUOIT', 'ALKYD', 'GLARY', 'BEAMY', 'HEXAD', 'BONKS', 'TECUM', 'KERBS', 'FILAR', 'FRIER', 'REDUX', 'ABUZZ', 'FADER', 'SHOER', 'COUTH', 'TRUES', 'GUYED', 'GOONY', 'BOOKY', 'FUZES', 'HURLY',
'GENET', 'HODAD', 'CALIX', 'FILER', 'PAWLS', 'IODIC', 'UTERO', 'HENGE', 'UNSAY', 'LIERS', 'PIING', 'WEALD', 'SEXED', 'FOLIC', 'POXED', 'CUNTS', 'ANILE', 'KITHS', 'BECKS', 'TATTY', 'PLENA', 'REBAR', 'ABLED', 'TOYER', 'ATTAR', 'TEAKS', 'AIOLI', 'AWING', 'ANENT',
'FECES', 'REDIP', 'WISTS', 'PRATS', 'MESNE', 'MUTER', 'SMURF', 'OWEST', 'BAHTS', 'LOSSY', 'FTPED', 'HUNKY', 'HOERS', 'SLIER', 'SICKS', 'FATLY', 'DELFT', 'HIVER', 'HIMBO', 'PENGO', 'BUSKS', 'LOXES', 'ZONKS', 'ILIUM', 'APORT', 'IKONS', 'MULCT', 'REEVE', 'CIVVY',
'CANNA', 'BARFY', 'KAIAK', 'SCUDO', 'KNOUT', 'GAPER', 'BHANG', 'PEASE', 'UTERI', 'LASES', 'PATEN', 'RASAE', 'AXELS', 'STOAS', 'OMBRE', 'STYLI', 'GUNKY', 'HAZER', 'KENAF', 'AHOYS', 'AMMOS', 'WEENY', 'URGER', 'KUDZU', 'PAREN', 'BOLOS', 'FETOR', 'NITTY', 'TECHY',
'LIETH', 'SOMAS', 'DARKY', 'VILLI', 'GLUON', 'JANES', 'CANTS', 'FARTS', 'SOCLE', 'JINNS', 'RUING', 'SLILY', 'RICER', 'HADDA', 'WOWEE', 'RICES', 'NERTS', 'CAULS', 'SWIVE', 'LILTY', 'MICKS', 'ARITY', 'PASHA', 'FINIF', 'OINKY', 'GUTTY', 'TETRA', 'WISES', 'WOLDS',
'BALDS', 'PICOT', 'WHATS', 'SHIKI', 'BUNGS', 'SNARF', 'LEGOS', 'DUNGS', 'STOGY', 'BERMS', 'TANGS', 'VAILS', 'ROODS', 'MOREL', 'SWARE', 'ELANS', 'LATUS', 'GULES', 'RAZER', 'DOXIE', 'BUENA', 'OVERS', 'GUTTA', 'ZINCS', 'NATES', 'KIRKS', 'TIKES', 'DONEE', 'JERRY',
'MOHEL', 'CEDER', 'DOGES', 'UNMAP', 'FOLIA', 'RAWLY', 'SNARK', 'TOPOI', 'CEILS', 'IMMIX', 'YORES', 'DIEST', 'BUBBA', 'POMPS', 'FORKY', 'TURDY', 'LAWZY', 'POOHS', 'WORTS', 'GLOMS', 'BEANO', 'MULEY', 'BARKY', 'TUNNY', 'AURIC', 'FUNKS', 'GAFFS', 'CORDY', 'CURDY',
'LISLE', 'TORIC', 'SOYAS', 'REMAN', 'MUNGY', 'CARPY', 'APISH', 'OATEN', 'GAPPY', 'AURAE', 'BRACT', 'ROOKY', 'AXLED', 'BURRY', 'SIZER', 'PROEM', 'TURFY', 'IMPRO', 'MASHY', 'MIENS', 'NONNY', 'OLIOS', 'GROOK', 'SATES', 'AGLEY', 'CORGI', 'DASHY', 'DOSER', 'DILDO',
'APSOS', 'XORED', 'LAKER', 'PLAYA', 'SELAH', 'MALTY', 'DULSE', 'FRIGS', 'DEMIT', 'WHOSO', 'RIALS', 'SAWER', 'SPICS', 'BEDIM', 'SNUGS', 'FANIN', 'AZOIC', 'ICERS', 'SUERS', 'WIZEN', 'KOINE', 'TOPOS', 'SHIRR', 'RIFER', 'FERAL', 'LADED', 'LASED', 'TURDS', 'SWEDE',
'EASTS', 'COZEN', 'UNHIT', 'PALLY', 'AITCH', 'SEDUM', 'COPER', 'RUCHE', 'GEEKS', 'SWAGS', 'ETEXT', 'ALGIN', 'OFFED', 'NINJA', 'HOLER', 'DOTER', 'TOTER', 'BESOT', 'DICUT', 'MACER', 'PEENS', 'PEWIT', 'REDOX', 'POLER', 'YECCH', 'FLUKY', 'DOETH', 'TWATS', 'CRUDS',
'BEBUG', 'BIDER', 'STELE', 'HEXER', 'WESTS', 'GLUER', 'PILAU', 'ABAFT', 'WHELM', 'LACER', 'INODE', 'TABUS', 'GATOR', 'CUING', 'REFLY', 'LUTED', 'CUKES', 'BAIRN', 'BIGHT', 'ARSES', 'CRUMP', 'LOGGY', 'BLINI', 'SPOOR', 'TOYON', 'HARKS', 'WAZOO', 'FENNY', 'NAVES',
'KEYER', 'TUFAS', 'MORPH', 'RAJAS', 'TYPAL', 'SPIFF', 'OXLIP', 'UNBAN', 'MUSSY', 'FINNY', 'RIMER', 'LOGIN', 'MOLAS', 'CIRRI', 'HUZZA', 'AGONE', 'UNSEX', 'UNWON', 'PEATS', 'TOILE', 'ZOMBI', 'DEWED', 'NOOKY', 'ALKYL', 'IXNAY', 'DOVEY', 'HOLEY', 'CUBER', 'AMYLS',
'PODIA', 'CHINO', 'APNEA', 'PRIMS', 'LYCRA', 'JOHNS', 'PRIMO', 'FATWA', 'EGGER', 'HEMPY', 'SNOOK', 'HYING', 'FUZED', 'BARMS', 'CRINK', 'MOOTS', 'YERBA', 'RHUMB', 'UNARC', 'DIRER', 'MUNGE', 'ELAND', 'NARES', 'WRIER', 'NODDY', 'ATILT', 'JUKES', 'ENDER', 'THENS',
'UNFIX', 'DOGGO', 'ZOOKS', 'DIDDY', 'SHMOO', 'BRUSK', 'PREST', 'CURER', 'PASTS', 'KELPY', 'BOCCE', 'KICKY', 'TAROS', 'LINGS', 'DICKY', 'NERDY', 'ABEND', 'STELA', 'BIGGY', 'LAVED', 'BALDY', 'PUBIS', 'GOOKS', 'WONKY', 'STIED', 'HYPOS', 'ASSED', 'SPUMY', 'OSIER',
'ROBLE', 'RUMBA', 'BIFFY', 'PUPAL','VIBES', 'GASSY', 'UNLIT', 'NERVY', 'FEMME', 'BITER', 'FICHE', 'BOORS', 'GAFFE', 'SAXES', 'RECAP', 'SYNCH', 'FACIE', 'DICEY', 'OUIJA', 'HEWER', 'LEGIT', 'GURUS', 'EDIFY', 'TWEAK', 'CARON', 'TYPOS', 'RERUN', 'POLLY', 'SURDS',
'HAMZA', 'NULLS', 'HATER', 'LEFTY', 'MOGUL', 'MAFIA', 'DEBUG', 'PATES', 'BLABS', 'SPLAY', 'TALUS', 'PORNO', 'MOOLA', 'NIXED', 'KILOS', 'SNIDE', 'HORSY', 'GESSO', 'JAGGY', 'TROVE', 'NIXES', 'CREEL', 'PATER', 'IOTAS', 'CADGE', 'SKYED', 'HOKUM', 'FURZE', 'ANKHS',
'CURIE', 'NUTSY', 'HILUM', 'REMIX', 'ANGST', 'BURLS', 'JIMMY', 'VEINY', 'TRYST', 'CODON', 'BEFOG', 'GAMED', 'FLUME', 'AXMAN', 'DOOZY', 'LUBES', 'RHEAS', 'BOZOS', 'BUTYL', 'KELLY', 'MYNAH', 'JOCKS', 'DONUT', 'AVIAN', 'WURST', 'CHOCK', 'QUASH', 'QUALS', 'HAYED',
'BOMBE', 'CUSHY', 'SPACY', 'PUKED', 'LEERY', 'THEWS', 'PRINK', 'AMENS', 'TESLA', 'INTRO', 'FIVER', 'FRUMP', 'CAPOS', 'OPINE', 'CODER', 'NAMER', 'JOWLY', 'PUKES', 'HALED', 'CHARD', 'DUFFS', 'BRUIN', 'REUSE', 'WHANG', 'TOONS', 'FRATS', 'SILTY', 'TELEX', 'CUTUP',
'NISEI', 'NEATO', 'DECAF', 'SOFTY', 'BIMBO', 'ADLIB', 'LOONY', 'SHOED', 'AGUES', 'PEEVE', 'NOWAY', 'GAMEY', 'SARGE', 'RERAN', 'EPACT', 'POTTY', 'CONED', 'UPEND', 'NARCO', 'IKATS', 'WHORL', 'JINKS', 'TIZZY', 'WEEPY', 'POSIT', 'MARGE', 'VEGAN', 'CLOPS', 'NUMBS',
'REEKS', 'RUBES', 'ROWER', 'BIPED', 'TIFFS', 'HOCUS', 'HAMMY', 'BUNCO', 'FIXIT', 'TYKES', 'CHAWS', 'YUCKY', 'HOKEY', 'RESEW', 'MAVEN', 'ADMAN', 'SCUZZ', 'SLOGS', 'SOUSE', 'NACHO', 'MIMED', 'MELDS', 'BOFFO', 'DEBIT', 'PINUP', 'VAGUS', 'GULAG', 'RANDY', 'BOSUN',
'EDUCE', 'FAXES', 'AURAS', 'PESTO', 'ANTSY', 'BETAS', 'FIZZY', 'DORKY', 'SNITS', 'MOXIE', 'THANE', 'MYLAR', 'NOBBY', 'GAMIN', 'GOUTY', 'ESSES', 'GOYIM', 'PANED', 'DRUID', 'JADES', 'REHAB', 'GOFER', 'TZARS', 'OCTET', 'HOMED', 'SOCKO', 'DORKS', 'EARED', 'ANTED',
'ELIDE', 'FAZES', 'OXBOW', 'DOWSE', 'SITUS', 'MACAW', 'SCONE', 'DRILY', 'HYPER', 'SALSA', 'MOOCH', 'GATED', 'UNJAM', 'LIPID', 'MITRE', 'VENAL', 'KNISH', 'RITZY', 'DIVAS', 'TORUS', 'MANGE', 'DIMER', 'RECUT', 'MESON', 'WINED', 'FENDS', 'PHAGE', 'FIATS', 'CAULK',
'CAVIL', 'PANTY', 'ROANS', 'BILKS', 'HONES', 'BOTCH', 'ESTOP', 'SULLY', 'SOOTH', 'GELDS', 'AHOLD', 'RAPER', 'PAGER', 'FIXER', 'INFIX', 'HICKS', 'TUXES', 'PLEBE', 'TWITS', 'ABASH', 'TWIXT', 'WACKO', 'PRIMP', 'NABLA', 'GIRTS', 'MIFFS', 'EMOTE', 'XEROX', 'REBID',
'SHAHS', 'RUTTY', 'GROUT', 'GRIFT', 'DEIFY', 'BIDDY', 'KOPEK', 'SEMIS', 'BRIES', 'ACMES', 'PITON', 'HUSSY', 'TORTS', 'DISCO', 'WHORE', 'BOOZY', 'GIBED', 'VAMPS', 'AMOUR', 'SOPPY', 'GONZO', 'DURST', 'WADER', 'TUTUS', 'PERMS', 'CATTY', 'GLITZ', 'BRIGS', 'NERDS',
'BARMY', 'GIZMO', 'OWLET', 'SAYER', 'MOLLS', 'SHARD', 'WHOPS', 'COMPS', 'CORER', 'COLAS', 'MATTE', 'DROID', 'PLOYS', 'VAPID', 'CAIRN', 'DEISM', 'MIXUP', 'YIKES', 'PROSY', 'RAKER', 'FLUBS', 'WHISH', 'REIFY', 'CRAPS', 'SHAGS', 'CLONE', 'HAZED', 'MACHO', 'RECTO',
'REFIX', 'DRAMS', 'BIKER', 'AQUAS', 'PORKY', 'DOYEN', 'EXUDE', 'GOOFS', 'DIVVY', 'NOELS', 'JIVED', 'HULKY', 'CAGER', 'HARPY', 'OLDIE', 'VIVAS', 'ADMIX', 'CODAS', 'ZILCH', 'DEIST', 'ORCAS', 'RETRO', 'PILAF', 'PARSE', 'RANTS', 'ZINGY', 'TODDY', 'CHIFF', 'MICRO',
'VEEPS', 'GIRLY', 'NEXUS', 'DEMOS', 'BIBBS', 'ANTES', 'LULUS', 'GNARL', 'ZIPPY', 'IVIED', 'EPEES', 'WIMPS', 'TROMP', 'GRAIL', 'YOYOS', 'POUFS', 'HALES', 'ROUST', 'CABAL', 'RAWER', 'PAMPA', 'MOSEY', 'KEFIR', 'BURGS', 'UNMET', 'CUSPY', 'BOOBS', 'BOONS', 'HYPES',
'DYNES', 'NARDS', 'LANAI', 'YOGIS', 'SEPAL', 'QUARK', 'TOKED', 'PRATE', 'AYINS', 'HAWED', 'SWIGS', 'VITAS', 'TOKER', 'DOPER', 'BOSSA', 'LINTY', 'FOIST', 'MONDO', 'STASH', 'KAYOS', 'TWERP', 'ZESTY', 'CAPON', 'WIMPY', 'REWED', 'FUNGO', 'TAROT', 'FROSH', 'KABOB',
'PINKO', 'REDID', 'MIMEO', 'HEIST', 'TARPS', 'LAMAS', 'SUTRA', 'DINAR', 'WHAMS', 'BUSTY', 'SPAYS', 'MAMBO', 'NABOB', 'PREPS', 'ODOUR', 'CABBY', 'CONKS', 'SLUFF', 'DADOS', 'HOURI', 'SWART', 'BALMS', 'GUTSY', 'FAXED', 'EGADS', 'PUSHY', 'RETRY', 'AGORA', 'DRUBS',
'DAFFY', 'CHITS', 'MUFTI', 'KARMA', 'LOTTO', 'TOFFS', 'BURPS', 'DEUCE', 'ZINGS', 'KAPPA', 'CLADS', 'DOGGY', 'DUPER', 'SCAMS', 'OGLER', 'MIMES', 'THROE', 'ZETAS', 'WALED', 'PROMO', 'BLATS', 'MUFFS', 'OINKS', 'VIAND', 'COSET', 'FINKS', 'FADDY', 'MINIS', 'SNAFU',
'SAUNA', 'USURY', 'MUXES', 'CRAWS', 'STATS', 'CONDO', 'COXES', 'LOOPY', 'DORMS', 'ASCOT', 'DIPPY', 'EXECS', 'DOPEY', 'ENVOI', 'UMPTY', 'GISMO', 'FAZED', 'STROP', 'JIVES', 'SLIMS', 'BATIK', 'PINGS', 'SONLY', 'LEGGO', 'PEKOE', 'PRAWN', 'LUAUS', 'CAMPY', 'OODLE',
'PREXY', 'PROMS', 'TOUTS', 'OGLES', 'TWEET', 'TOADY', 'NAIAD', 'HIDER', 'NUKED', 'FATSO', 'SLUTS', 'OBITS', 'NARCS', 'TYROS', 'DELIS', 'WOOER', 'HYPED', 'POSET', 'BYWAY', 'TEXAS', 'SCROD', 'AVOWS', 'FUTON', 'TORTE', 'TUPLE', 'CAROM', 'KEBAB', 'TAMPS', 'JILTS',
'DUALS', 'ARTSY', 'REPRO', 'MODEM', 'TOPED', 'PSYCH', 'SICKO', 'KLUTZ', 'TARNS', 'COXED', 'DRAYS', 'CLOYS', 'ANDED', 'PIKER', 'AIMER', 'SURAS', 'LIMOS', 'FLACK', 'HAPAX', 'DUTCH', 'MUCKY', 'SHIRE', 'KLIEG', 'STAPH', 'LAYUP', 'TOKES', 'AXING', 'TOPER', 'DUVET',
'COWRY', 'PROFS', 'BLAHS', 'ADDLE', 'SUDSY', 'BATTY', 'COIFS', 'SUETY', 'GABBY', 'HAFTA', 'PITAS', 'GOUDA', 'DEICE', 'TAUPE', 'TOPES', 'DUCHY', 'NITRO', 'CARNY', 'LIMEY', 'ORALS', 'HIRER', 'TAXER', 'ROILS', 'RUBLE', 'ELATE', 'DOLOR', 'WRYER', 'SNOTS', 'QUAIS',
'COKED', 'GIMEL', 'GORSE', 'MINAS', 'GOEST', 'AGAPE', 'MANTA', 'JINGS', 'ILIAC', 'ADMEN', 'OFFEN', 'CILLS', 'OFFAL', 'LOTTA', 'BOLAS', 'THWAP', 'ALWAY', 'BOGGY', 'DONNA', 'LOCOS', 'BELAY', 'GLUEY', 'BITSY', 'MIMSY', 'HILAR', 'OUTTA', 'VROOM', 'FETAL', 'RATHS',
'RENAL', 'DYADS', 'CROCS', 'VIRES', 'CULPA', 'KIVAS', 'FEIST', 'TEATS', 'THATS', 'YAWLS', 'WHENS', 'ABACA', 'OHHHH', 'APHIS', 'FUSTY', 'ECLAT', 'PERDU', 'MAYST', 'EXEAT', 'MOLLY', 'SUPRA', 'WETLY', 'PLASM', 'BUFFA', 'SEMEN', 'PUKKA', 'TAGUA', 'PARAS', 'STOAT',
'SECCO', 'CARTE', 'HAUTE', 'MOLAL', 'SHADS', 'FORMA', 'OVOID', 'PIONS', 'MODUS', 'BUENO', 'RHEUM', 'SCURF', 'PARER', 'EPHAH', 'DOEST', 'SPRUE', 'FLAMS', 'MOLTO', 'DIETH', 'CHOOS', 'MIKED', 'BRONX', 'GOOPY', 'BALLY', 'PLUMY', 'MOONY', 'MORTS', 'YOURN', 'BIPOD',
'SPUME', 'ALGAL', 'AMBIT', 'MUCHO', 'SPUED', 'DOZER', 'HARUM', 'GROAT', 'SKINT', 'LAUDE', 'THRUM', 'PAPPY', 'ONCET', 'RIMED', 'GIGUE', 'LIMED', 'PLEIN', 'REDLY', 'HUMPF', 'LITES', 'SEEST', 'GREBE', 'ABSIT', 'THANX', 'PSHAW', 'YAWPS', 'PLATS', 'PAYED', 'AREAL',
'TILTH', 'YOUSE', 'GWINE', 'THEES', 'WATSA', 'LENTO', 'SPITZ', 'YAWED', 'GIPSY', 'SPRAT', 'CORNU', 'AMAHS', 'BLOWY', 'WAHOO', 'LUBRA', 'MECUM', 'WHOOO', 'COQUI', 'SABRA', 'EDEMA', 'MRADS', 'DICOT', 'ASTRO', 'KITED', 'OUZEL', 'DIDOS', 'GRATA', 'BONNE', 'AXMEN',
'KLUNK', 'SUMMA', 'LAVES', 'PURLS', 'YAWNY', 'TEARY', 'MASSE', 'LARGO', 'BAZAR', 'PSSST', 'SYLPH', 'LULAB', 'TOQUE', 'FUGIT', 'PLUNK', 'ORTHO', 'LUCRE', 'COOCH', 'WHIPT', 'FOLKY', 'TYRES', 'WHEEE', 'CORKY', 'INJUN', 'SOLON', 'DIDOT', 'KERFS', 'RAYED', 'WASSA',
'CHILE', 'BEGAT', 'NIPPY', 'LITRE', 'MAGNA', 'REBOX', 'HYDRO', 'MILCH', 'BRENT', 'GYVES', 'LAZED', 'FEUED', 'MAVIS', 'INAPT', 'BAULK', 'CASUS', 'SCRUM', 'WISED', 'FOSSA', 'DOWER', 'KYRIE', 'BHOYS', 'SCUSE', 'FEUAR', 'OHMIC', 'JUSTE', 'UKASE', 'BEAUX', 'TUSKY',
'ORATE', 'MUSTA', 'LARDY', 'INTRA', 'QUIFF', 'EPSOM', 'NEATH', 'OCHER', 'TARED', 'HOMME', 'MEZZO', 'CORMS', 'PSOAS', 'BEAKY', 'TERRY', 'INFRA', 'SPIVS', 'TUANS', 'BELLI', 'BERGS', 'ANIMA', 'WEIRS', 'MAHUA', 'SCOPS', 'MANSE', 'TITRE', 'CURIA', 'KEBOB', 'CYCAD',
'TALKY', 'FUCKS', 'TAPIS', 'AMIDE', 'DOLCE', 'SLOES', 'JAKES', 'RUSSE', 'BLASH', 'TUTTI', 'PRUTA', 'PANGA', 'BLEBS', 'TENCH', 'SWARF', 'HEREM', 'MISSY', 'MERSE', 'PAWKY', 'LIMEN', 'VIVRE', 'CHERT', 'UNSEE', 'TIROS', 'BRACK', 'FOOTS', 'WELSH', 'FOSSE', 'KNOPS',
'ILEUM', 'NOIRE', 'FIRMA', 'PODGY', 'LAIRD', 'THUNK', 'SHUTE', 'ROWAN', 'SHOJI', 'POESY', 'UNCAP', 'FAMES', 'GLEES', 'COSTA', 'TURPS', 'FORES', 'SOLUM', 'IMAGO', 'BYRES', 'FONDU', 'CONEY', 'POLIS', 'DICTU', 'KRAAL', 'SHERD', 'MUMBO', 'WROTH', 'CHARS', 'UNBOX',
'VACUO', 'SLUED', 'WEEST', 'HADES', 'WILED', 'SYNCS', 'MUSER', 'EXCON', 'HOARS', 'SIBYL', 'PASSE', 'JOEYS', 'LOTSA', 'LEPTA', 'SHAYS', 'BOCKS', 'ENDUE', 'DARER', 'NONES', 'ILEUS', 'PLASH', 'BUSBY', 'WHEAL', 'BUFFO', 'YOBBO', 'BILES', 'POXES', 'ROOTY', 'LICIT',
'TERCE', 'BROMO', 'HAYEY', 'DWEEB', 'IMBED', 'SARAN', 'BRUIT', 'PUNKY', 'SOFTS', 'BIFFS', 'LOPPY', 'AGARS', 'AQUAE', 'LIVRE', 'BIOME', 'BUNDS', 'SHEWS', 'DIEMS', 'GINNY', 'DEGUM', 'POLOS', 'DESEX', 'UNMAN', 'DUNGY', 'VITAM', 'WEDGY', 'GLEBE', 'APERS', 'RIDGY',
'ROIDS', 'WIFEY', 'VAPES', 'WHOAS', 'BUNKO', 'YOLKY', 'ULNAS', 'REEKY', 'BODGE', 'BRANT', 'DAVIT', 'DEQUE', 'LIKER', 'JENNY', 'TACTS', 'FULLS', 'TREAP', 'LIGNE', 'ACKED', 'REFRY', 'VOWER', 'AARGH', 'CHURL', 'MOMMA', 'GAOLS', 'WHUMP', 'ARRAS', 'MARLS', 'TILER',
'GROGS', 'MEMES', 'MIDIS', 'TIDED', 'HALER', 'DUCES', 'TWINY', 'POSTE', 'UNRIG', 'PRISE', 'DRABS', 'QUIDS', 'FACER', 'SPIER', 'BARIC', 'GEOID', 'REMAP', 'TRIER', 'GUNKS', 'STENO', 'STOMA', 'AIRER', 'OVATE', 'TORAH', 'APIAN', 'SMUTS', 'POCKS', 'YURTS', 'EXURB',
'DEFOG', 'NUDER', 'BOSKY', 'NIMBI', 'MOTHY', 'JOYED', 'LABIA', 'PARDS', 'JAMMY', 'BIGLY', 'FAXER', 'HOPPY', 'NURBS', 'COTES', 'DISHY', 'VISED', 'CELEB', 'PISMO','PALLS', 'MOPES', 'BONED', 'WISPY', 'RAVED', 'SWAPS', 'JUNKY', 'DOILY', 'PAWNS', 'TAMER', 'POACH',
'BAITS', 'DAMNS', 'GUMBO', 'DAUNT', 'PRANK', 'HUNKS', 'BUXOM', 'HERES', 'HONKS', 'STOWS', 'UNBAR', 'IDLES', 'ROUTS', 'SAGES', 'GOADS', 'REMIT', 'COPES', 'DEIGN', 'CULLS', 'GIRDS', 'HAVES', 'LUCKS', 'STUNK', 'DODOS', 'SHAMS', 'SNUBS', 'ICONS', 'USURP', 'DOOMS',
'HELLS', 'SOLED', 'COMAS', 'PAVES', 'MATHS', 'PERKS', 'LIMPS', 'WOMBS', 'BLURB', 'DAUBS', 'COKES', 'SOURS', 'STUNS', 'CASED', 'MUSTS', 'COEDS', 'COWED', 'APING', 'ZONED', 'RUMMY', 'FETES', 'SKULK', 'QUAFF', 'RAJAH', 'DEANS', 'REAPS', 'GALAS', 'TILLS', 'ROVED',
'KUDOS', 'TONED', 'PARED', 'SCULL', 'VEXES', 'PUNTS', 'SNOOP', 'BAILS', 'DAMES', 'HAZES', 'LORES', 'MARTS', 'VOIDS', 'AMEBA', 'RAKES', 'ADZES', 'HARMS', 'REARS', 'SATYR', 'SWILL', 'HEXES', 'COLIC', 'LEEKS', 'HURLS', 'YOWLS', 'IVIES', 'PLOPS', 'MUSKS', 'PAPAW',
'JELLS', 'BUSED', 'CRUET', 'BIDED', 'FILCH', 'ZESTS', 'ROOKS', 'LAXLY', 'RENDS', 'LOAMS', 'BASKS', 'SIRES', 'CARPS', 'POKEY', 'FLITS', 'MUSES', 'BAWLS', 'SHUCK', 'VILER', 'LISPS', 'PEEPS', 'SORER', 'LOLLS', 'PRUDE', 'DIKED', 'FLOSS', 'FLOGS', 'SCUMS', 'DOPES',
'BOGIE', 'PINKY', 'LEAFS', 'TUBAS', 'SCADS', 'LOWED', 'YESES', 'BIKED', 'QUALM', 'EVENS', 'CANED', 'GAWKS', 'WHITS', 'WOOLY', 'GLUTS', 'ROMPS', 'BESTS', 'DUNCE', 'CRONY', 'JOIST', 'TUNAS', 'BONER', 'MALLS', 'PARCH', 'AVERS', 'CRAMS', 'PARES', 'DALLY', 'BIGOT',
'KALES', 'FLAYS', 'LEACH', 'GUSHY', 'POOCH', 'HUGER', 'SLYER', 'GOLFS', 'MIRES', 'FLUES', 'LOAFS', 'ARCED', 'ACNES', 'NEONS', 'FIEFS', 'DINTS', 'DAZES', 'POUTS', 'CORED', 'YULES', 'LILTS', 'BEEFS', 'MUTTS', 'FELLS', 'COWLS', 'SPUDS', 'LAMES', 'JAWED', 'DUPES',
'DEADS', 'BYLAW', 'NOONS', 'NIFTY', 'CLUED', 'VIREO', 'GAPES', 'METES', 'CUTER', 'MAIMS', 'DROLL', 'CUPID', 'MAULS', 'SEDGE', 'PAPAS', 'WHEYS', 'EKING', 'LOOTS', 'HILTS', 'MEOWS', 'BEAUS', 'DICES', 'PEPPY', 'RIPER', 'FOGEY', 'GISTS', 'YOGAS', 'GILTS', 'SKEWS',
'CEDES', 'ZEALS', 'ALUMS', 'OKAYS', 'ELOPE', 'GRUMP', 'WAFTS', 'SOOTS', 'BLIMP', 'HEFTS', 'MULLS', 'HOSED', 'CRESS', 'DOFFS', 'RUDER', 'PIXIE', 'WAIFS', 'OUSTS', 'PUCKS', 'BIERS', 'GULCH', 'SUETS', 'HOBOS', 'LINTS', 'BRANS', 'TEALS', 'GARBS', 'PEWEE', 'HELMS',
'TURFS', 'QUIPS', 'WENDS', 'BANES', 'NAPES', 'ICIER', 'SWATS', 'BAGEL', 'HEXED', 'OGRES', 'GONER', 'GILDS', 'PYRES', 'LARDS', 'BIDES', 'PAGED', 'TALON', 'FLOUT', 'MEDIC', 'VEALS', 'PUTTS', 'DIRKS', 'DOTES', 'TIPPY', 'BLURT', 'PITHS', 'ACING', 'BARER', 'WHETS',
'GAITS', 'WOOLS', 'DUNKS', 'HEROS', 'SWABS', 'DIRTS', 'JUTES', 'HEMPS', 'SURFS', 'OKAPI', 'CHOWS', 'SHOOS', 'DUSKS', 'PARRY', 'DECAL', 'FURLS', 'CILIA', 'SEARS', 'NOVAE', 'MURKS', 'WARPS', 'SLUES', 'LAMER', 'SARIS', 'WEANS', 'PURRS', 'DILLS', 'TOGAS', 'NEWTS',
'MEANY', 'BUNTS', 'RAZES', 'GOONS', 'WICKS', 'RUSES', 'VENDS', 'GEODE', 'DRAKE', 'JUDOS', 'LOFTS', 'PULPS', 'LAUDS', 'MUCKS', 'VISES', 'MOCHA', 'OILED', 'ROMAN', 'ETHYL', 'GOTTA', 'FUGUE', 'SMACK', 'GOURD', 'BUMPY', 'RADIX', 'FATTY', 'BORAX', 'CUBIT', 'CACTI',
'GAMMA', 'FOCAL', 'AVAIL', 'PAPAL', 'GOLLY', 'ELITE', 'VERSA', 'BILLY', 'ADIEU', 'ANNUM', 'HOWDY', 'RHINO', 'NORMS', 'BOBBY', 'AXIOM', 'SETUP', 'YOLKS', 'TERNS', 'MIXER', 'GENRE', 'KNOLL', 'ABODE', 'JUNTA', 'GORGE', 'COMBO', 'ALPHA', 'OVERT', 'KINDA', 'SPELT',
'PRICK', 'NOBLY', 'EPHOD', 'AUDIO', 'MODAL', 'VELDT', 'WARTY', 'FLUKE', 'BONNY', 'BREAM', 'ROSIN', 'BOLLS', 'DOERS', 'DOWNS', 'BEADY', 'MOTIF', 'HUMPH', 'FELLA', 'MOULD', 'CREPE', 'KERNS', 'ALOHA', 'GLYPH', 'AZURE', 'RISER', 'BLEST', 'LOCUS', 'LUMPY', 'BERYL',
'WANNA', 'BRIER', 'TUNER', 'ROWDY', 'MURAL', 'TIMER', 'CANST', 'KRILL', 'QUOTH', 'LEMME', 'TRIAD', 'TENON', 'AMPLY', 'DEEPS', 'PADRE', 'LEANT', 'PACER', 'OCTAL', 'DOLLY', 'TRANS', 'SUMAC', 'FOAMY', 'LOLLY', 'GIVER', 'QUIPU', 'CODEX', 'MANNA', 'UNWED', 'VODKA',
'FERNY', 'SALON', 'DUPLE', 'BORON', 'REVUE', 'CRIER', 'ALACK', 'INTER', 'DILLY', 'WHIST', 'CULTS', 'SPAKE', 'RESET', 'LOESS', 'DECOR', 'MOVER', 'VERVE', 'ETHIC', 'GAMUT', 'LINGO', 'DUNNO', 'ALIGN', 'SISSY', 'INCUR', 'REEDY', 'AVANT', 'PIPER', 'WAXER', 'CALYX',
'BASIL', 'COONS', 'SEINE', 'PINEY', 'LEMMA', 'TRAMS', 'WINCH', 'WHIRR', 'SAITH', 'IONIC', 'HEADY', 'HAREM', 'TUMMY', 'SALLY', 'SHIED', 'DROSS', 'FARAD', 'SAVER', 'TILDE', 'JINGO', 'BOWER', 'SERIF', 'FACTO', 'BELLE', 'INSET', 'BOGUS', 'CAVED', 'FORTE', 'SOOTY',
'BONGO', 'TOVES', 'CREDO', 'BASAL', 'YELLA', 'AGLOW', 'GLEAN', 'GUSTO', 'HYMEN', 'ETHOS', 'TERRA', 'BRASH', 'SCRIP', 'SWASH', 'ALEPH', 'TINNY', 'ITCHY', 'WANTA', 'TRICE', 'JOWLS', 'GONGS', 'GARDE', 'BORIC', 'TWILL', 'SOWER', 'HENRY', 'AWASH', 'LIBEL', 'SPURN',
'SABRE', 'REBUT', 'PENAL', 'OBESE', 'SONNY', 'QUIRT', 'MEBBE', 'TACIT', 'GREEK', 'XENON', 'HULLO', 'PIQUE', 'ROGER', 'NEGRO', 'HADST', 'GECKO', 'BEGET', 'UNCUT', 'ALOES', 'LOUIS', 'QUINT', 'CLUNK', 'RAPED', 'SALVO', 'DIODE', 'MATEY', 'HERTZ', 'XYLEM', 'KIOSK',
'APACE', 'CAWED', 'PETER', 'WENCH', 'COHOS', 'SORTA', 'GAMBA', 'BYTES', 'TANGO', 'NUTTY', 'AXIAL', 'ALECK', 'NATAL', 'CLOMP', 'GORED', 'SIREE', 'BANDY', 'GUNNY', 'RUNIC', 'WHIZZ', 'RUPEE', 'FATED', 'WIPER', 'BARDS', 'BRINY', 'STAID', 'HOCKS', 'OCHRE', 'YUMMY',
'GENTS', 'SOUPY', 'ROPER', 'SWATH', 'CAMEO', 'EDGER', 'SPATE', 'GIMME', 'EBBED', 'BREVE', 'THETA', 'DEEMS', 'DYKES', 'SERVO', 'TELLY', 'TABBY', 'TARES', 'BLOCS', 'WELCH', 'GHOUL', 'VITAE', 'CUMIN', 'DINKY', 'BRONC', 'TABOR', 'TEENY', 'COMER', 'BORER', 'SIRED',
'PRIVY', 'MAMMY', 'DEARY', 'GYROS', 'SPRIT', 'CONGA', 'QUIRE', 'THUGS', 'FUROR', 'BLOKE', 'RUNES', 'BAWDY', 'CADRE', 'TOXIN', 'ANNUL', 'EGGED', 'ANION', 'NODES', 'PICKY', 'STEIN', 'JELLO', 'AUDIT', 'ECHOS', 'FAGOT', 'LETUP', 'EYRIE', 'FOUNT', 'CAPED', 'AXONS',
'AMUCK', 'BANAL', 'RILED', 'PETIT', 'UMBER', 'MILER', 'FIBRE', 'AGAVE', 'BATED', 'BILGE', 'VITRO', 'FEINT', 'PUDGY', 'MATER', 'MANIC', 'UMPED', 'PESKY', 'STREP', 'SLURP', 'PYLON', 'PUREE', 'CARET', 'TEMPS', 'NEWEL', 'YAWNS', 'SEEDY', 'TREED', 'COUPS', 'RANGY',
'BRADS', 'MANGY', 'LONER', 'CIRCA', 'TIBIA', 'AFOUL', 'MOMMY', 'TITER', 'CARNE', 'KOOKY', 'MOTES', 'AMITY', 'SUAVE', 'HIPPO', 'CURVY', 'SAMBA', 'NEWSY', 'ANISE', 'IMAMS', 'TULLE', 'AWAYS', 'LIVEN', 'HALLO', 'WALES', 'OPTED', 'CANTO', 'IDYLL', 'BODES', 'CURIO',
'WRACK', 'HIKER', 'CHIVE', 'YOKEL', 'DOTTY', 'DEMUR', 'CUSPS', 'SPECS', 'QUADS', 'LAITY', 'TONER', 'DECRY', 'WRITS', 'SAUTE', 'CLACK', 'AUGHT', 'LOGOS', 'TIPSY', 'NATTY', 'DUCAL', 'BIDET', 'BULGY', 'METRE', 'LUSTS', 'UNARY', 'GOETH', 'BALER', 'SITED', 'SHIES',
'HASPS', 'BRUNG', 'HOLED', 'SWANK', 'LOOKY', 'MELEE', 'HUFFY', 'LOAMY', 'PIMPS', 'TITAN', 'BINGE', 'SHUNT', 'FEMUR', 'LIBRA', 'SEDER', 'HONED', 'ANNAS', 'COYPU', 'SHIMS', 'ZOWIE', 'JIHAD', 'SAVVY', 'NADIR', 'BASSO', 'MONIC', 'MANED', 'MOUSY', 'OMEGA', 'LAVER',
'PRIMA', 'PICAS', 'FOLIO', 'MECCA', 'REALS', 'TROTH', 'TESTY', 'BALKY', 'CRIMP', 'CHINK', 'ABETS', 'SPLAT', 'ABACI', 'VAUNT', 'CUTIE', 'PASTY', 'MORAY', 'LEVIS', 'RATTY', 'ISLET', 'JOUST', 'MOTET', 'VIRAL', 'NUKES', 'GRADS', 'COMFY', 'VOILA', 'WOOZY', 'BLUED',
'WHOMP', 'SWARD', 'METRO', 'SKEET', 'CHINE', 'AERIE', 'BOWIE', 'TUBBY', 'EMIRS', 'COATI', 'UNZIP', 'SLOBS', 'TRIKE', 'FUNKY', 'DUCAT', 'DEWEY', 'SKOAL', 'WADIS', 'OOMPH', 'TAKER', 'MINIM', 'GETUP', 'STOIC', 'SYNOD', 'RUNTY', 'FLYBY', 'BRAZE', 'INLAY', 'VENUE',
'LOUTS', 'PEATY', 'ORLON', 'HUMPY', 'RADON', 'BEAUT', 'RASPY', 'UNFED', 'CRICK', 'NAPPY', 'VIZOR', 'YIPES', 'REBUS', 'DIVOT', 'KIWIS', 'VETCH', 'SQUIB', 'SITAR', 'KIDDO', 'DYERS', 'COTTA', 'MATZO', 'LAGER', 'ZEBUS', 'CRASS', 'DACHA', 'KNEED', 'DICTA', 'FAKIR',
'KNURL', 'RUNNY', 'UNPIN', 'JULEP', 'GLOBS', 'NUDES', 'SUSHI', 'TACKY', 'STOKE', 'KAPUT', 'BUTCH', 'HULAS', 'CROFT', 'ACHOO', 'GENII', 'NODAL', 'OUTGO', 'SPIEL', 'VIOLS', 'FETID', 'CAGEY', 'FUDGY', 'EPOXY', 'LEGGY', 'HANKY', 'LAPIS', 'FELON', 'BEEFY', 'COOTS',
'MELBA', 'CADDY', 'SEGUE', 'BETEL', 'FRIZZ', 'DREAR', 'KOOKS', 'TURBO', 'HOAGY', 'MOULT', 'HELIX', 'ZONAL', 'ARIAS', 'NOSEY', 'PAEAN', 'LACEY', 'BANNS', 'SWAIN', 'FRYER', 'RETCH', 'TENET', 'GIGAS', 'WHINY', 'OGLED', 'RUMEN', 'BEGOT', 'CRUSE', 'ABUTS', 'RIVEN',
'BALKS', 'SINES', 'SIGMA', 'ABASE', 'ENNUI', 'GORES', 'UNSET', 'AUGUR', 'SATED', 'ODIUM', 'LATIN', 'DINGS', 'MOIRE', 'SCION', 'HENNA', 'KRAUT', 'DICKS', 'LIFER', 'PRIGS', 'BEBOP', 'GAGES', 'GAZER', 'FANNY', 'GIBES', 'AURAL', 'TEMPI', 'HOOCH', 'RAPES', 'SNUCK',
'HARTS', 'TECHS', 'EMEND', 'NINNY', 'GUAVA', 'SCARP', 'LIEGE', 'TUFTY', 'SEPIA', 'TOMES', 'CAROB', 'EMCEE', 'PRAMS', 'POSER', 'VERSO', 'HUBBA', 'JOULE', 'BAIZE', 'BLIPS', 'SCRIM', 'CUBBY', 'CLAVE', 'WINOS', 'REARM', 'LIENS', 'LUMEN', 'CHUMP', 'NANNY', 'TRUMP',
'FICHU', 'CHOMP', 'HOMOS', 'PURTY', 'MASER', 'WOOSH', 'PATSY', 'SHILL', 'RUSKS', 'AVAST', 'SWAMI', 'BODED', 'AHHHH', 'LOBED', 'NATCH', 'SHISH', 'TANSY', 'SNOOT', 'PAYER', 'ALTHO', 'SAPPY', 'LAXER', 'HUBBY', 'AEGIS', 'RILES', 'DITTO', 'JAZZY', 'DINGO', 'QUASI',
'SEPTA', 'PEAKY', 'LORRY', 'HEERD', 'BITTY', 'PAYEE', 'SEAMY', 'APSES', 'IMBUE', 'BELIE', 'CHARY', 'SPOOF', 'PHYLA', 'CLIME', 'BABEL', 'WACKY', 'SUMPS', 'SKIDS', 'KHANS', 'CRYPT', 'INURE', 'NONCE', 'OUTEN', 'FAIRE', 'HOOEY', 'ANOLE', 'KAZOO', 'CALVE', 'LIMBO',
'ARGOT', 'DUCKY', 'FAKER','GNATS', 'BOUTS', 'SISAL', 'SHUTS', 'HOSES', 'DRYLY', 'HOVER', 'GLOSS', 'SEEPS', 'DENIM', 'PUTTY', 'GUPPY', 'LEAKY', 'DUSKY', 'FILTH', 'OBOES', 'SPANS', 'FOWLS', 'ADORN', 'GLAZE', 'HAUNT', 'DARES', 'OBEYS', 'BAKES', 'ABYSS', 'SMELT',
'GANGS', 'ACHES', 'TRAWL', 'CLAPS', 'UNDID', 'SPICY', 'HOIST', 'FADES', 'VICAR', 'ACORN', 'PUSSY', 'GRUFF', 'MUSTY', 'TARTS', 'SNUFF', 'HUNCH', 'TRUCE', 'TWEED', 'DRYER', 'LOSER', 'SHEAF', 'MOLES', 'LAPSE', 'TAWNY', 'VEXED', 'AUTOS', 'WAGER', 'DOMES', 'SHEEN',
'CLANG', 'SPADE', 'SOWED', 'BROIL', 'SLYLY', 'STUDS', 'GRUNT', 'DONOR', 'SLUGS', 'ASPEN', 'HOMER', 'CROAK', 'TITHE', 'HALTS', 'AVERT', 'HAVOC', 'HOGAN', 'GLINT', 'RUDDY', 'JEEPS', 'FLAKY', 'LADLE', 'TAUNT', 'SNORE', 'FINES', 'PROPS', 'PRUNE', 'PESOS', 'RADII',
'POKES', 'TILED', 'DAISY', 'HERON', 'VILLA', 'FARCE', 'BINDS', 'CITES', 'FIXES', 'JERKS', 'LIVID', 'WAKED', 'INKED', 'BOOMS', 'CHEWS', 'LICKS', 'HYENA', 'SCOFF', 'LUSTY', 'SONIC', 'SMITH', 'USHER', 'TUCKS', 'VIGIL', 'MOLTS', 'SECTS', 'SPARS', 'DUMPS', 'SCALY',
'WISPS', 'SORES', 'MINCE', 'PANDA', 'FLIER', 'AXLES', 'PLIED', 'BOOBY', 'PATIO', 'RABBI', 'PETAL', 'POLYP', 'TINTS', 'GRATE', 'TROLL', 'TOLLS', 'RELIC', 'PHONY', 'BLEAT', 'FLAWS', 'FLAKE', 'SNAGS', 'APTLY', 'DRAWL', 'ULCER', 'SOAPY', 'BOSSY', 'MONKS', 'CRAGS',
'CAGED', 'TWANG', 'DINER', 'TAPED', 'CADET', 'GRIDS', 'SPAWN', 'GUILE', 'NOOSE', 'MORES', 'GIRTH', 'SLIMY', 'AIDES', 'SPASM', 'BURRS', 'ALIBI', 'LYMPH', 'SAUCY', 'MUGGY', 'LITER', 'JOKED', 'GOOFY', 'EXAMS', 'ENACT', 'STORK', 'LURED', 'TOXIC', 'OMENS', 'NEARS',
'COVET', 'WRUNG', 'FORUM', 'VENOM', 'MOODY', 'ALDER', 'SASSY', 'FLAIR', 'GUILD', 'PRAYS', 'WRENS', 'HAULS', 'STAVE', 'TILTS', 'PECKS', 'STOMP', 'GALES', 'TEMPT', 'CAPES', 'MESAS', 'OMITS', 'TEPEE', 'HARRY', 'WRING', 'EVOKE', 'LIMES', 'CLUCK', 'LUNGE', 'HIGHS',
'CANES', 'GIDDY', 'LITHE', 'VERGE', 'KHAKI', 'QUEUE', 'LOATH', 'FOYER', 'OUTDO', 'FARED', 'DETER', 'CRUMB', 'ASTIR', 'SPIRE', 'JUMPY', 'EXTOL', 'BUOYS', 'STUBS', 'LUCID', 'THONG', 'AFORE', 'WHIFF', 'MAXIM', 'HULLS', 'CLOGS', 'SLATS', 'JIFFY', 'ARBOR', 'CINCH',
'IGLOO', 'GOODY', 'GAZES', 'DOWEL', 'CALMS', 'BITCH', 'SCOWL', 'GULPS', 'CODED', 'WAVER', 'MASON', 'LOBES', 'EBONY', 'FLAIL', 'ISLES', 'CLODS', 'DAZED', 'ADEPT', 'OOZED', 'SEDAN', 'CLAYS', 'WARTS', 'KETCH', 'SKUNK', 'MANES', 'ADORE', 'SNEER', 'MANGO', 'FIORD',
'FLORA', 'ROOMY', 'MINKS', 'THAWS', 'WATTS', 'FREER', 'EXULT', 'PLUSH', 'PALED', 'TWAIN', 'CLINK', 'SCAMP', 'PAWED', 'GROPE', 'BRAVO', 'GABLE', 'STINK', 'SEVER', 'WANED', 'RARER', 'REGAL', 'WARDS', 'FAWNS', 'BABES', 'UNIFY', 'AMEND', 'OAKEN', 'GLADE', 'VISOR',
'HEFTY', 'NINES', 'THROB', 'PECAN', 'BUTTS', 'PENCE', 'SILLS', 'JAILS', 'FLYER', 'SABER', 'NOMAD', 'MITER', 'BEEPS', 'DOMED', 'GULFS', 'CURBS', 'HEATH', 'MOORS', 'AORTA', 'LARKS', 'TANGY', 'WRYLY', 'CHEEP', 'RAGES', 'EVADE', 'LURES', 'FREAK', 'VOGUE', 'TUNIC',
'SLAMS', 'KNITS', 'DUMPY', 'MANIA', 'SPITS', 'FIRTH', 'HIKES', 'TROTS', 'NOSED', 'CLANK', 'DOGMA', 'BLOAT', 'BALSA', 'GRAFT', 'MIDDY', 'STILE', 'KEYED', 'FINCH', 'SPERM', 'CHAFF', 'WILES', 'AMIGO', 'COPRA', 'AMISS', 'EYING', 'TWIRL', 'LURCH', 'POPES', 'CHINS',
'SMOCK', 'TINES', 'GUISE', 'GRITS', 'JUNKS', 'SHOAL', 'CACHE', 'TAPIR', 'ATOLL', 'DEITY', 'TOILS', 'SPREE', 'MOCKS', 'SCANS', 'SHORN', 'REVEL', 'RAVEN', 'HOARY', 'REELS', 'SCUFF', 'MIMIC', 'WEEDY', 'CORNY', 'TRUER', 'ROUGE', 'EMBER', 'FLOES', 'TORSO', 'WIPES',
'EDICT', 'SULKY', 'RECUR', 'GROIN', 'BASTE', 'KINKS', 'SURER', 'PIGGY', 'MOLDY', 'FRANC', 'LIARS', 'INEPT', 'GUSTY', 'FACET', 'JETTY', 'EQUIP', 'LEPER', 'SLINK', 'SOARS', 'CATER', 'DOWRY', 'SIDED', 'YEARN', 'DECOY', 'TABOO', 'OVALS', 'HEALS', 'PLEAS', 'BERET',
'SPILT', 'GAYLY', 'ROVER', 'ENDOW', 'PYGMY', 'CARAT', 'ABBEY', 'VENTS', 'WAKEN', 'CHIMP', 'FUMED', 'SODAS', 'VINYL', 'CLOUT', 'WADES', 'MITES', 'SMIRK', 'BORES', 'BUNNY', 'SURLY', 'FROCK', 'FORAY', 'PURER', 'MILKS', 'QUERY', 'MIRED', 'BLARE', 'FROTH', 'GRUEL',
'NAVEL', 'PALER', 'PUFFY', 'CASKS', 'GRIME', 'DERBY', 'MAMMA', 'GAVEL', 'TEDDY', 'VOMIT', 'MOANS', 'ALLOT', 'DEFER', 'WIELD', 'VIPER', 'LOUSE', 'ERRED', 'HEWED', 'ABHOR', 'WREST', 'WAXEN', 'ADAGE', 'ARDOR', 'STABS', 'PORED', 'RONDO', 'LOPED', 'FISHY', 'BIBLE',
'HIRES', 'FOALS', 'FEUDS', 'JAMBS', 'THUDS', 'JEERS', 'KNEAD', 'QUIRK', 'RUGBY', 'EXPEL', 'GREYS', 'RIGOR', 'ESTER', 'LYRES', 'ABACK', 'GLUES', 'LOTUS', 'LURID', 'RUNGS', 'HUTCH', 'THYME', 'VALET', 'TOMMY', 'YOKES', 'EPICS', 'TRILL', 'PIKES', 'OZONE', 'CAPER',
'CHIME', 'FREES', 'FAMED', 'LEECH', 'SMITE', 'NEIGH', 'ERODE', 'ROBED', 'HOARD', 'SALVE', 'CONIC', 'GAWKY', 'CRAZE', 'JACKS', 'GLOAT', 'MUSHY', 'RUMPS', 'FETUS', 'WINCE', 'PINKS', 'SHALT', 'TOOTS', 'GLENS', 'COOED', 'RUSTS', 'STEWS', 'SHRED', 'PARKA', 'CHUGS',
'WINKS', 'CLOTS', 'SHREW', 'BOOED', 'FILMY', 'JUROR', 'DENTS', 'GUMMY', 'GRAYS', 'HOOKY', 'BUTTE', 'DOGIE', 'POLED', 'REAMS', 'FIFES', 'SPANK', 'GAYER', 'TEPID', 'SPOOK', 'TAINT', 'FLIRT', 'ROGUE', 'SPIKY', 'OPALS', 'MISER', 'COCKY', 'COYLY', 'BALMY', 'SLOSH',
'BRAWL', 'APHID', 'FAKED', 'HYDRA', 'BRAGS', 'CHIDE', 'YANKS', 'ALLAY', 'VIDEO', 'ALTOS', 'EASES', 'METED', 'CHASM', 'LONGS', 'EXCEL', 'TAFFY', 'IMPEL', 'SAVOR', 'KOALA', 'QUAYS', 'DAWNS', 'PROXY', 'CLOVE', 'DUETS', 'DREGS', 'TARDY', 'BRIAR', 'GRIMY', 'ULTRA',
'MEATY', 'HALVE', 'WAILS', 'SUEDE', 'MAUVE', 'ENVOY', 'ARSON', 'COVES', 'GOOEY', 'BREWS', 'SOFAS', 'CHUMS', 'AMAZE', 'ZOOMS', 'ABBOT', 'HALOS', 'SCOUR', 'SUING', 'CRIBS', 'SAGAS', 'ENEMA', 'WORDY', 'HARPS', 'COUPE', 'MOLAR', 'FLOPS', 'WEEPS', 'MINTS', 'ASHEN',
'FELTS', 'ASKEW', 'MUNCH', 'MEWED', 'DIVAN', 'VICES', 'JUMBO', 'BLOBS', 'BLOTS', 'SPUNK', 'ACRID', 'TOPAZ', 'CUBED', 'CLANS', 'FLEES', 'SLURS', 'GNAWS', 'WELDS', 'FORDS', 'EMITS', 'AGATE', 'PUMAS', 'MENDS', 'DARKS', 'DUKES', 'PLIES', 'CANNY', 'HOOTS', 'OOZES',
'LAMED', 'FOULS', 'CLEFS', 'NICKS', 'MATED', 'SKIMS', 'BRUNT', 'TUBER', 'TINGE', 'FATES', 'DITTY', 'THINS', 'FRETS', 'EIDER', 'BAYOU', 'MULCH', 'FASTS', 'AMASS', 'DAMPS', 'MORNS', 'FRIAR', 'PALSY', 'VISTA', 'CROON', 'CONCH', 'UDDER', 'TACOS', 'SKITS', 'MIKES',
'QUITS', 'PREEN', 'ASTER', 'ADDER', 'ELEGY', 'PULPY', 'SCOWS', 'BALED', 'HOVEL', 'LAVAS', 'CRAVE', 'OPTIC', 'WELTS', 'BUSTS', 'KNAVE', 'RAZED', 'SHINS', 'TOTES', 'SCOOT', 'DEARS', 'CROCK', 'MUTES', 'TRIMS', 'SKEIN', 'DOTED', 'SHUNS', 'VEERS', 'FAKES', 'YOKED',
'WOOED', 'HACKS', 'SPRIG', 'WANDS', 'LULLS', 'SEERS', 'SNOBS', 'NOOKS', 'PINED', 'PERKY', 'MOOED', 'FRILL', 'DINES', 'BOOZE', 'TRIPE', 'PRONG', 'DRIPS', 'ODDER', 'LEVEE', 'ANTIC', 'SIDLE', 'PITHY', 'CORKS', 'YELPS', 'JOKER', 'FLECK', 'BUFFS', 'SCRAM', 'TIERS',
'BOGEY', 'DOLED', 'IRATE', 'VALES', 'COPED', 'HAILS', 'ELUDE', 'BULKS', 'AIRED', 'VYING', 'STAGS', 'STREW', 'COCCI', 'PACTS', 'SCABS', 'SILOS', 'DUSTS', 'YODEL', 'TERSE', 'JADED', 'BASER', 'JIBES', 'FOILS', 'SWAYS', 'FORGO', 'SLAYS', 'PREYS', 'TREKS', 'QUELL',
'PEEKS', 'ASSAY', 'LURKS', 'EJECT', 'BOARS', 'TRITE', 'BELCH', 'GNASH', 'WANES', 'LUTES', 'WHIMS', 'DOSED', 'CHEWY', 'SNIPE', 'UMBRA', 'TEEMS', 'DOZES', 'KELPS', 'UPPED', 'BRAWN', 'DOPED', 'SHUSH', 'RINDS', 'SLUSH', 'MORON', 'VOILE', 'WOKEN', 'FJORD', 'SHEIK',
'JESTS', 'KAYAK', 'SLEWS', 'TOTED', 'SANER', 'DRAPE', 'PATTY', 'RAVES', 'SULFA', 'GRIST', 'SKIED', 'VIXEN', 'CIVET', 'VOUCH', 'TIARA', 'HOMEY', 'MOPED', 'RUNTS', 'SERGE', 'KINKY', 'RILLS', 'CORNS', 'BRATS', 'PRIES', 'AMBLE', 'FRIES', 'LOONS', 'TSARS', 'DATUM',
'MUSKY', 'PIGMY', 'GNOME', 'RAVEL', 'OVULE', 'ICILY', 'LIKEN', 'LEMUR', 'FRAYS', 'SILTS', 'SIFTS', 'PLODS', 'RAMPS', 'TRESS', 'EARLS', 'DUDES', 'WAIVE', 'KARAT', 'JOLTS', 'PEONS', 'BEERS', 'HORNY', 'PALES', 'WREAK', 'LAIRS', 'LYNCH', 'STANK', 'SWOON', 'IDLER',
'ABORT', 'BLITZ', 'ENSUE', 'ATONE', 'BINGO', 'ROVES', 'KILTS', 'SCALD', 'ADIOS', 'CYNIC', 'DULLS', 'MEMOS', 'ELFIN', 'DALES', 'PEELS', 'PEALS', 'BARES', 'SINUS', 'CRONE', 'SABLE', 'HINDS', 'SHIRK', 'ENROL', 'WILTS', 'ROAMS', 'DUPED', 'CYSTS', 'MITTS', 'SAFES',
'SPATS', 'COOPS', 'FILET', 'KNELL', 'REFIT', 'COVEY', 'PUNKS', 'KILNS', 'FITLY', 'ABATE', 'TALCS', 'HEEDS', 'DUELS', 'WANLY', 'RUFFS', 'GAUSS', 'LAPEL', 'JAUNT', 'WHELP', 'CLEAT', 'GAUZY', 'DIRGE', 'EDITS', 'WORMY', 'MOATS', 'SMEAR', 'PRODS', 'BOWEL', 'FRISK',
'VESTS', 'BAYED', 'RASPS', 'TAMES', 'DELVE', 'EMBED', 'BEFIT', 'WAFER', 'CEDED', 'NOVAS', 'FEIGN', 'SPEWS', 'LARCH', 'HUFFS', 'DOLES', 'MAMAS', 'HULKS', 'PRIED', 'BRIMS', 'IRKED', 'ASPIC', 'SWIPE', 'MEALY', 'SKIMP', 'BLUER', 'SLAKE', 'DOWDY', 'PENIS', 'BRAYS',
'PUPAS', 'EGRET', 'FLUNK', 'PHLOX', 'GRIPE', 'PEONY', 'DOUSE', 'BLURS', 'DARNS', 'SLUNK', 'LEFTS', 'CHATS', 'INANE', 'VIALS', 'STILT', 'RINKS', 'WOOFS', 'WOWED', 'BONGS', 'FROND', 'INGOT', 'EVICT', 'SINGE', 'SHYER', 'FLIED', 'SLOPS', 'DOLTS', 'DROOL', 'DELLS',
'WHELK', 'HIPPY', 'FETED', 'ETHER', 'COCOS', 'HIVES', 'JIBED', 'MAZES', 'TRIOS', 'SIRUP', 'SQUAB', 'LATHS', 'LEERS', 'PASTA', 'RIFTS', 'LOPES', 'ALIAS', 'WHIRS', 'DICED', 'SLAGS', 'LODES', 'FOXED', 'IDLED', 'PROWS', 'PLAIT', 'MALTS', 'CHAFE', 'COWER', 'TOYED',
'CHEFS', 'KEELS', 'STIES', 'RACER', 'ETUDE', 'SUCKS', 'SULKS', 'MICAS', 'CZARS', 'COPSE', 'AILED', 'ABLER', 'RABID', 'GOLDS', 'CROUP', 'SNAKY', 'VISAS', 'DRUNK', 'RESTS', 'CHILL', 'SLAIN', 'PANIC', 'CORDS', 'TUNED', 'CRISP', 'LEDGE', 'DIVED', 'SWAMP', 'CLUNG',
'STOLE', 'MOLDS', 'YARNS', 'LIVER', 'GAUGE', 'BREED', 'STOOL', 'GULLS', 'AWOKE', 'GROSS', 'DIARY', 'RAILS', 'BELLY', 'TREND', 'FLASK', 'STAKE', 'FRIED', 'DRAWS', 'ACTOR', 'HANDY', 'BOWLS', 'HASTE', 'SCOPE', 'DEALS', 'KNOTS', 'MOONS', 'ESSAY', 'THUMP', 'HANGS',
'BLISS', 'DEALT', 'GAINS', 'BOMBS', 'CLOWN', 'PALMS', 'CONES', 'ROAST', 'TIDAL', 'BORED', 'CHANT', 'ACIDS', 'DOUGH', 'CAMPS', 'SWORE', 'LOVER', 'HOOKS', 'MALES', 'COCOA', 'PUNCH', 'AWARD', 'REINS', 'NINTH', 'NOSES', 'LINKS', 'DRAIN', 'FILLS', 'NYLON', 'LUNAR',
'PULSE', 'FLOWN', 'ELBOW', 'FATAL', 'SITES', 'MOTHS', 'MEATS', 'FOXES', 'MINED', 'ATTIC', 'FIERY', 'MOUNT', 'USAGE', 'SWEAR', 'SNOWY', 'RUSTY', 'SCARE', 'TRAPS', 'RELAX', 'REACT', 'VALID', 'ROBIN', 'CEASE', 'GILLS', 'PRIOR', 'SAFER', 'POLIO', 'LOYAL', 'SWELL',
'SALTY', 'MARSH', 'VAGUE', 'WEAVE', 'MOUND', 'SEALS', 'MULES', 'VIRUS', 'SCOUT', 'ACUTE', 'WINDY', 'STOUT', 'FOLDS', 'SEIZE', 'HILLY', 'JOINS', 'PLUCK', 'STACK', 'LORDS', 'DUNES', 'BURRO', 'HAWKS', 'TROUT', 'FEEDS', 'SCARF', 'HALLS', 'COALS', 'TOWEL', 'SOULS',
'ELECT', 'BUGGY', 'PUMPS', 'LOANS', 'SPINS', 'FILES', 'OXIDE', 'PAINS', 'PHOTO', 'RIVAL', 'FLATS', 'SYRUP', 'RODEO', 'SANDS', 'MOOSE', 'PINTS', 'CURLY', 'COMIC', 'CLOAK', 'ONION', 'CLAMS', 'SCRAP', 'DIDST', 'COUCH', 'CODES', 'FAILS', 'OUNCE', 'LODGE', 'GREET',
'GYPSY', 'UTTER', 'PAVED', 'ZONES', 'FOURS', 'ALLEY', 'TILES', 'BLESS', 'CREST', 'ELDER', 'KILLS', 'YEAST', 'ERECT', 'BUGLE', 'MEDAL', 'ROLES', 'HOUND', 'SNAIL', 'ALTER', 'ANKLE', 'RELAY', 'LOOPS', 'ZEROS', 'BITES', 'MODES', 'DEBTS', 'REALM', 'GLOVE', 'RAYON',
'SWIMS', 'POKED', 'STRAY', 'LIFTS', 'MAKER', 'LUMPS', 'GRAZE', 'DREAD', 'BARNS', 'DOCKS', 'MASTS', 'POURS', 'WHARF', 'CURSE', 'PLUMP', 'ROBES', 'SEEKS', 'CEDAR', 'CURLS', 'JOLLY', 'MYTHS', 'CAGES', 'GLOOM', 'LOCKS', 'PEDAL', 'BEETS', 'CROWS', 'ANODE', 'SLASH',
'CREEP', 'ROWED', 'CHIPS', 'FISTS', 'WINES', 'CARES', 'VALVE', 'NEWER', 'MOTEL', 'IVORY', 'NECKS', 'CLAMP', 'BARGE', 'BLUES', 'ALIEN', 'FROWN', 'STRAP', 'CREWS', 'SHACK', 'GONNA', 'SAVES', 'STUMP', 'FERRY', 'IDOLS', 'COOKS', 'JUICY', 'GLARE', 'CARTS', 'ALLOY',
'BULBS', 'LAWNS', 'LASTS', 'FUELS', 'ODDLY', 'CRANE', 'FILED', 'WEIRD', 'SHAWL', 'SLIPS', 'TROOP', 'BOLTS', 'SUITE', 'SLEEK', 'QUILT', 'TRAMP', 'BLAZE', 'ATLAS', 'ODORS', 'SCRUB', 'CRABS', 'PROBE', 'LOGIC', 'ADOBE', 'EXILE', 'REBEL', 'GRIND', 'STING', 'SPINE',
'CLING', 'DESKS', 'GROVE', 'LEAPS', 'PROSE', 'LOFTY', 'AGONY', 'SNARE', 'TUSKS', 'BULLS', 'MOODS', 'HUMID', 'FINER', 'DIMLY', 'PLANK', 'CHINA', 'PINES', 'GUILT', 'SACKS', 'BRACE', 'QUOTE', 'LATHE', 'GAILY', 'FONTS', 'SCALP', 'ADOPT', 'FOGGY', 'FERNS', 'GRAMS',
'CLUMP', 'PERCH', 'TUMOR', 'TEENS', 'CRANK', 'FABLE', 'HEDGE', 'GENES', 'SOBER', 'BOAST', 'TRACT', 'CIGAR', 'UNITE', 'OWING', 'THIGH', 'HAIKU', 'SWISH', 'DIKES', 'WEDGE', 'BOOTH', 'EASED', 'FRAIL', 'COUGH', 'TOMBS', 'DARTS', 'FORTS', 'CHOIR', 'POUCH', 'PINCH',
'HAIRY', 'BUYER', 'TORCH', 'VIGOR', 'WALTZ', 'HEATS', 'HERBS', 'USERS', 'FLINT', 'CLICK', 'MADAM', 'BLEAK', 'BLUNT', 'AIDED', 'LACKS', 'MASKS', 'WADED', 'RISKS', 'NURSE', 'CHAOS', 'SEWED', 'CURED', 'AMPLE', 'LEASE', 'STEAK', 'SINKS', 'MERIT', 'BLUFF', 'BATHE',
'GLEAM', 'BONUS', 'COLTS', 'SHEAR', 'GLAND', 'SILKY', 'SKATE', 'BIRCH', 'ANVIL', 'SLEDS', 'GROAN', 'MAIDS', 'MEETS', 'SPECK', 'HYMNS', 'HINTS', 'DROWN', 'BOSOM', 'SLICK', 'QUEST', 'COILS', 'SPIED', 'SNOWS', 'STEAD', 'SNACK', 'PLOWS', 'BLOND', 'TAMED', 'THORN',
'WAITS', 'GLUED', 'BANJO', 'TEASE', 'ARENA', 'BULKY', 'CARVE', 'STUNT', 'WARMS', 'SHADY', 'RAZOR', 'FOLLY', 'LEAFY', 'NOTCH', 'FOOLS', 'OTTER', 'PEARS', 'FLUSH', 'GENUS', 'ACHED', 'FIVES', 'FLAPS', 'SPOUT', 'SMOTE', 'FUMES', 'ADAPT', 'CUFFS', 'TASTY', 'STOOP',
'CLIPS', 'DISKS', 'SNIFF', 'LANES', 'BRISK', 'IMPLY', 'DEMON', 'SUPER', 'FURRY', 'RAGED', 'GROWL', 'TEXTS', 'HARDY', 'STUNG', 'TYPED', 'HATES', 'WISER', 'TIMID', 'SERUM', 'BEAKS', 'ROTOR', 'CASTS', 'BATHS', 'GLIDE', 'PLOTS', 'TRAIT', 'RESIN', 'SLUMS', 'LYRIC',
'PUFFS', 'DECKS', 'BROOD', 'MOURN', 'ALOFT', 'ABUSE', 'WHIRL', 'EDGED', 'OVARY', 'QUACK', 'HEAPS', 'SLANG', 'AWAIT', 'CIVIC', 'SAINT', 'BEVEL', 'SONAR', 'AUNTS', 'PACKS', 'FROZE', 'TONIC', 'CORPS', 'SWARM', 'FRANK', 'REPAY', 'GAUNT', 'WIRED', 'NIECE', 'CELLO',
'NEEDY', 'CHUCK', 'STONY', 'MEDIA', 'SURGE', 'HURTS', 'REPEL', 'HUSKY', 'DATED', 'HUNTS', 'MISTS', 'EXERT', 'DRIES', 'MATES', 'SWORN', 'BAKER', 'SPICE', 'OASIS', 'BOILS', 'SPURS', 'DOVES', 'SNEAK', 'PACES', 'COLON', 'SIEGE', 'STRUM', 'DRIER', 'CACAO', 'HUMUS',
'BALES', 'PIPED', 'NASTY', 'RINSE', 'BOXER', 'SHRUB', 'AMUSE', 'TACKS', 'CITED', 'SLUNG', 'DELTA', 'LADEN', 'LARVA', 'RENTS', 'YELLS', 'SPOOL', 'SPILL', 'CRUSH', 'JEWEL', 'SNAPS', 'STAIN', 'KICKS', 'TYING', 'SLITS', 'RATED', 'EERIE', 'SMASH', 'PLUMS', 'ZEBRA',
'EARNS', 'BUSHY', 'SCARY', 'SQUAD', 'TUTOR', 'SILKS', 'SLABS', 'BUMPS', 'EVILS', 'FANGS', 'SNOUT', 'PERIL', 'PIVOT', 'YACHT', 'LOBBY', 'JEANS', 'GRINS', 'VIOLA', 'LINER', 'COMET', 'SCARS', 'CHOPS', 'RAIDS', 'EATER', 'SLATE', 'SKIPS', 'SOLES', 'MISTY', 'URINE',
'KNOBS', 'SLEET', 'HOLLY', 'PESTS', 'FORKS', 'GRILL', 'TRAYS', 'PAILS', 'BORNE', 'TENOR', 'WARES', 'CAROL', 'WOODY', 'CANON', 'WAKES', 'KITTY', 'MINER', 'POLLS', 'SHAKY', 'NASAL', 'SCORN', 'CHESS', 'TAXIS', 'CRATE', 'SHYLY', 'TULIP', 'FORGE', 'NYMPH', 'BUDGE',
'LOWLY', 'ABIDE', 'DEPOT', 'OASES', 'ASSES', 'SHEDS', 'FUDGE', 'PILLS', 'RIVET', 'THINE', 'GROOM', 'LANKY', 'BOOST', 'BROTH', 'HEAVE', 'GRAVY', 'BEECH', 'TIMED', 'QUAIL', 'INERT', 'GEARS', 'CHICK', 'HINGE', 'TRASH', 'CLASH', 'SIGHS', 'RENEW', 'BOUGH', 'DWARF',
'SLOWS', 'QUILL', 'SHAVE', 'SPORE', 'SIXES', 'CHUNK', 'MADLY', 'PACED', 'BRAID', 'FUZZY', 'MOTTO', 'SPIES', 'SLACK', 'MUCUS', 'MAGMA', 'AWFUL', 'DISCS', 'ERASE', 'POSED', 'ASSET', 'CIDER', 'TAPER', 'THEFT', 'CHURN', 'SATIN', 'SLOTS', 'TAXED', 'BULLY', 'SLOTH',
'SHALE', 'TREAD', 'RAKED', 'CURDS', 'MANOR', 'AISLE', 'BULGE', 'LOINS', 'STAIR', 'TAPES', 'LEANS', 'BUNKS', 'SQUAT', 'TOWED', 'LANCE', 'PANES', 'SAKES', 'HEIRS', 'CASTE', 'DUMMY', 'PORES', 'FAUNA', 'CROOK', 'POISE', 'EPOCH', 'RISKY', 'WARNS', 'FLING', 'BERRY',
'GRAPE', 'FLANK', 'DRAGS', 'SQUID', 'PELTS', 'ICING', 'IRONY', 'IRONS', 'BARKS', 'WHOOP', 'CHOKE', 'DIETS', 'WHIPS', 'TALLY', 'DOZED', 'TWINE', 'KITES', 'BIKES', 'TICKS', 'RIOTS', 'ROARS', 'VAULT', 'LOOMS', 'SCOLD', 'BLINK', 'DANDY', 'PUPAE', 'SIEVE', 'SPIKE',
'DUCTS', 'LENDS', 'PIZZA', 'BRINK', 'WIDEN', 'PLUMB', 'PAGAN', 'FEATS', 'BISON', 'SOGGY', 'SCOOP', 'ARGON', 'NUDGE', 'SKIFF', 'AMBER', 'SEXES', 'ROUSE', 'SALTS', 'HITCH', 'EXALT', 'LEASH', 'DINED', 'CHUTE', 'SNORT', 'GUSTS', 'MELON', 'CHEAT', 'REEFS', 'LLAMA',
'LASSO', 'DEBUT', 'QUOTA', 'OATHS', 'PRONE', 'MIXES', 'RAFTS', 'DIVES', 'STALE', 'INLET', 'FLICK', 'PINTO', 'BROWS', 'UNTIE', 'BATCH', 'GREED', 'CHORE', 'STIRS', 'BLUSH', 'ONSET', 'BARBS', 'VOLTS', 'BEIGE', 'SWOOP', 'PADDY', 'LACED', 'SHOVE', 'JERKY', 'POPPY',
'LEAKS', 'FARES', 'DODGE', 'GODLY', 'SQUAW', 'AFFIX', 'BRUTE', 'NICER', 'UNDUE', 'SNARL', 'MERGE', 'DOSES', 'SHOWY', 'DADDY', 'ROOST', 'VASES', 'SWIRL', 'PETTY', 'COLDS', 'CURRY', 'COBRA', 'GENIE', 'FLARE', 'MESSY', 'CORES', 'SOAKS', 'RIPEN', 'WHINE', 'AMINO',
'PLAID', 'SPINY', 'MOWED', 'BATON', 'PEERS', 'VOWED', 'PIOUS', 'SWANS', 'EXITS', 'AFOOT', 'PLUGS', 'IDIOM', 'CHILI', 'RITES', 'SERFS', 'CLEFT', 'BERTH', 'GRUBS', 'ANNEX', 'DIZZY', 'HASTY', 'LATCH', 'WASPS', 'MIRTH', 'BARON', 'PLEAD', 'ALOOF', 'AGING', 'PIXEL',
'BARED', 'MUMMY', 'HOTLY', 'AUGER', 'BUDDY', 'CHAPS', 'BADGE', 'STARK', 'FAIRS', 'GULLY', 'MUMPS', 'EMERY', 'FILLY', 'OVENS', 'DRONE', 'GAUZE', 'IDIOT', 'FUSSY', 'ANNOY', 'SHANK', 'GOUGE', 'BLEED', 'ELVES', 'ROPED', 'UNFIT', 'BAGGY', 'MOWER', 'SCANT', 'GRABS',
'FLEAS', 'LOUSY', 'ALBUM', 'SAWED', 'COOKY', 'MURKY', 'INFER', 'BURLY', 'WAGED', 'DINGY', 'BRINE', 'KNEEL', 'CREAK', 'VANES', 'SMOKY', 'SPURT', 'COMBS', 'EASEL', 'LACES', 'HUMPS', 'RUMOR', 'AROMA', 'HORDE', 'SWISS', 'LEAPT', 'OPIUM', 'SLIME', 'AFIRE', 'PANSY',
'MARES', 'SOAPS', 'HUSKS', 'SNIPS', 'HAZEL', 'LINED', 'CAFES', 'NAIVE', 'WRAPS', 'SIZED', 'PIERS', 'BESET', 'AGILE', 'TONGS', 'STEED', 'FRAUD', 'BOOTY', 'VALOR', 'DOWNY', 'WITTY', 'MOSSY', 'PSALM', 'SCUBA', 'TOURS', 'POLKA', 'MILKY', 'GAUDY', 'SHRUG', 'TUFTS',
'WILDS', 'LASER', 'TRUSS', 'HARES', 'CREED', 'LILAC', 'SIREN', 'TARRY', 'BRIBE', 'SWINE', 'MUTED', 'FLIPS', 'CURES', 'SINEW', 'BOXED', 'HOOPS', 'GASPS', 'HOODS', 'NICHE', 'YUCCA', 'GLOWS', 'SEWER', 'WHACK', 'FUSES', 'GOWNS', 'DROOP', 'BUCKS', 'PANGS', 'MAILS',
'WHISK', 'HAVEN', 'CLASP', 'SLING', 'STINT', 'URGES', 'CHAMP', 'PIETY', 'CHIRP', 'PLEAT', 'POSSE', 'SUNUP', 'MENUS', 'HOWLS', 'QUAKE', 'KNACK', 'PLAZA', 'FIEND', 'CAKED', 'BANGS', 'ERUPT', 'POKER', 'OLDEN', 'CRAMP', 'VOTER', 'POSES', 'MANLY', 'SLUMP', 'FINED',
'GRIPS', 'GAPED', 'PURGE', 'HIKED', 'MAIZE', 'FLUFF', 'STRUT', 'SLOOP', 'PROWL', 'ROACH', 'COCKS', 'BLAND', 'DIALS', 'PLUME', 'SLAPS', 'SOUPS', 'DULLY', 'WILLS', 'FOAMS', 'SOLOS', 'SKIER', 'EAVES', 'TOTEM', 'FUSED', 'LATEX', 'VEILS', 'MUSED', 'MAINS', 'MYRRH',
'RACKS', 'GALLS','WHICH', 'THERE', 'THEIR', 'ABOUT', 'WOULD', 'THESE', 'OTHER', 'WORDS', 'COULD', 'WRITE', 'FIRST', 'WATER', 'AFTER', 'WHERE', 'RIGHT', 'THINK', 'THREE', 'YEARS', 'PLACE', 'SOUND', 'GREAT', 'AGAIN', 'STILL', 'EVERY', 'SMALL', 'FOUND', 'THOSE',
'NEVER', 'UNDER', 'MIGHT', 'WHILE', 'HOUSE', 'WORLD', 'BELOW', 'ASKED', 'GOING', 'LARGE', 'UNTIL', 'ALONG', 'SHALL', 'BEING', 'OFTEN', 'EARTH', 'BEGAN', 'SINCE', 'STUDY', 'NIGHT', 'LIGHT', 'ABOVE', 'PAPER', 'PARTS', 'YOUNG', 'STORY', 'POINT', 'TIMES', 'HEARD',
'WHOLE', 'WHITE', 'GIVEN', 'MEANS', 'MUSIC', 'MILES', 'THING', 'TODAY', 'LATER', 'USING', 'MONEY', 'LINES', 'ORDER', 'GROUP', 'AMONG', 'LEARN', 'KNOWN', 'SPACE', 'TABLE', 'EARLY', 'TREES', 'SHORT', 'HANDS', 'STATE', 'BLACK', 'SHOWN', 'STOOD', 'FRONT', 'VOICE',
'KINDS', 'MAKES', 'COMES', 'CLOSE', 'POWER', 'LIVED', 'VOWEL', 'TAKEN', 'BUILT', 'HEART', 'READY', 'QUITE', 'CLASS', 'BRING', 'ROUND', 'HORSE', 'SHOWS', 'PIECE', 'GREEN', 'STAND', 'BIRDS', 'START', 'RIVER', 'TRIED', 'LEAST', 'FIELD', 'WHOSE', 'GIRLS', 'LEAVE',
'ADDED', 'COLOR', 'THIRD', 'HOURS', 'MOVED', 'PLANT', 'DOING', 'NAMES', 'FORMS', 'HEAVY', 'IDEAS', 'CRIED', 'CHECK', 'FLOOR', 'BEGIN', 'WOMAN', 'ALONE', 'PLANE', 'SPELL', 'WATCH', 'CARRY', 'WROTE', 'CLEAR', 'NAMED', 'BOOKS', 'CHILD', 'GLASS', 'HUMAN', 'TAKES',
'PARTY', 'BUILD', 'SEEMS', 'BLOOD', 'SIDES', 'SEVEN', 'MOUTH', 'SOLVE', 'NORTH', 'VALUE', 'DEATH', 'MAYBE', 'HAPPY', 'TELLS', 'GIVES', 'LOOKS', 'SHAPE', 'LIVES', 'STEPS', 'AREAS', 'SENSE', 'SPEAK', 'FORCE', 'OCEAN', 'SPEED', 'WOMEN', 'METAL', 'SOUTH', 'GRASS',
'SCALE', 'CELLS', 'LOWER', 'SLEEP', 'WRONG', 'PAGES', 'SHIPS', 'NEEDS', 'ROCKS', 'EIGHT', 'MAJOR', 'LEVEL', 'TOTAL', 'AHEAD', 'REACH', 'STARS', 'STORE', 'SIGHT', 'TERMS', 'CATCH', 'WORKS', 'BOARD', 'COVER', 'SONGS', 'EQUAL', 'STONE', 'WAVES', 'GUESS', 'DANCE',
'SPOKE', 'BREAK', 'CAUSE', 'RADIO', 'WEEKS', 'LANDS', 'BASIC', 'LIKED', 'TRADE', 'FRESH', 'FINAL', 'FIGHT', 'MEANT', 'DRIVE', 'SPENT', 'LOCAL', 'WAXES', 'KNOWS', 'TRAIN', 'BREAD', 'HOMES', 'TEETH', 'COAST', 'THICK', 'BROWN', 'CLEAN', 'QUIET', 'SUGAR', 'FACTS',
'STEEL', 'FORTH', 'RULES', 'NOTES', 'UNITS', 'PEACE', 'MONTH', 'VERBS', 'SEEDS', 'HELPS', 'SHARP', 'VISIT', 'WOODS', 'CHIEF', 'WALLS', 'CROSS', 'WINGS', 'GROWN', 'CASES', 'FOODS', 'CROPS', 'FRUIT', 'STICK', 'WANTS', 'STAGE', 'SHEEP', 'NOUNS', 'PLAIN', 'DRINK',
'BONES', 'APART', 'TURNS', 'MOVES', 'TOUCH', 'ANGLE', 'BASED', 'RANGE', 'MARKS', 'TIRED', 'OLDER', 'FARMS', 'SPEND', 'SHOES', 'GOODS', 'CHAIR', 'TWICE', 'CENTS', 'EMPTY', 'ALIKE', 'STYLE', 'BROKE', 'PAIRS', 'COUNT', 'ENJOY', 'SCORE', 'SHORE', 'ROOTS', 'PAINT',
'HEADS', 'SHOOK', 'SERVE', 'ANGRY', 'CROWD', 'WHEEL', 'QUICK', 'DRESS', 'SHARE', 'ALIVE', 'NOISE', 'SOLID', 'CLOTH', 'SIGNS', 'HILLS', 'TYPES', 'DRAWN', 'WORTH', 'TRUCK', 'PIANO', 'UPPER', 'LOVED', 'USUAL', 'FACES', 'DROVE', 'CABIN', 'BOATS', 'TOWNS', 'PROUD',
'COURT', 'MODEL', 'PRIME', 'FIFTY', 'PLANS', 'YARDS', 'PROVE', 'TOOLS', 'PRICE', 'SHEET', 'SMELL', 'BOXES', 'RAISE', 'MATCH', 'TRUTH', 'ROADS', 'THREW', 'ENEMY', 'LUNCH', 'CHART', 'SCENE', 'GRAPH', 'DOUBT', 'GUIDE', 'WINDS', 'BLOCK', 'GRAIN', 'SMOKE', 'MIXED',
'GAMES', 'WAGON', 'SWEET', 'TOPIC', 'EXTRA', 'PLATE', 'TITLE', 'KNIFE', 'FENCE', 'FALLS', 'CLOUD', 'WHEAT', 'PLAYS', 'ENTER', 'BROAD', 'STEAM', 'ATOMS', 'PRESS', 'LYING', 'BASIS', 'CLOCK', 'TASTE', 'GROWS', 'THANK', 'STORM', 'AGREE', 'BRAIN', 'TRACK', 'SMILE',
'FUNNY', 'BEACH', 'STOCK', 'HURRY', 'SAVED', 'SORRY', 'GIANT', 'TRAIL', 'OFFER', 'OUGHT', 'ROUGH', 'DAILY', 'AVOID', 'KEEPS', 'THROW', 'ALLOW', 'CREAM', 'LAUGH', 'EDGES', 'TEACH', 'FRAME', 'BELLS', 'DREAM', 'MAGIC', 'OCCUR', 'ENDED', 'CHORD', 'FALSE', 'SKILL',
'HOLES', 'DOZEN', 'BRAVE', 'APPLE', 'CLIMB', 'OUTER', 'PITCH', 'RULER', 'HOLDS', 'FIXED', 'COSTS', 'CALLS', 'BLANK', 'STAFF', 'LABOR', 'EATEN', 'YOUTH', 'TONES', 'HONOR', 'GLOBE', 'GASES', 'DOORS', 'POLES', 'LOOSE', 'APPLY', 'TEARS', 'EXACT', 'BRUSH', 'CHEST',
'LAYER', 'WHALE', 'MINOR', 'FAITH', 'TESTS', 'JUDGE', 'ITEMS', 'WORRY', 'WASTE', 'HOPED', 'STRIP', 'BEGUN', 'ASIDE', 'LAKES', 'BOUND', 'DEPTH', 'CANDY', 'EVENT', 'WORSE', 'AWARE', 'SHELL', 'ROOMS', 'RANCH', 'IMAGE', 'SNAKE', 'ALOUD', 'DRIED', 'LIKES', 'MOTOR',
'POUND', 'KNEES', 'REFER', 'FULLY', 'CHAIN', 'SHIRT', 'FLOUR', 'DROPS', 'SPITE', 'ORBIT', 'BANKS', 'SHOOT', 'CURVE', 'TRIBE', 'TIGHT', 'BLIND', 'SLEPT', 'SHADE', 'CLAIM', 'FLIES', 'THEME', 'QUEEN', 'FIFTH', 'UNION', 'HENCE', 'STRAW', 'ENTRY', 'ISSUE', 'BIRTH',
'FEELS', 'ANGER', 'BRIEF', 'RHYME', 'GLORY', 'GUARD', 'FLOWS', 'FLESH', 'OWNED', 'TRICK', 'YOURS', 'SIZES', 'NOTED', 'WIDTH', 'BURST', 'ROUTE', 'LUNGS', 'UNCLE', 'BEARS', 'ROYAL', 'KINGS', 'FORTY', 'TRIAL', 'CARDS', 'BRASS', 'OPERA', 'CHOSE', 'OWNER', 'VAPOR',
'BEATS', 'MOUSE', 'TOUGH', 'WIRES', 'METER', 'TOWER', 'FINDS', 'INNER', 'STUCK', 'ARROW', 'POEMS', 'LABEL', 'SWING', 'SOLAR', 'TRULY', 'TENSE', 'BEANS', 'SPLIT', 'RISES', 'WEIGH', 'HOTEL', 'STEMS', 'PRIDE', 'SWUNG', 'GRADE', 'DIGIT', 'BADLY', 'BOOTS', 'PILOT',
'SALES', 'SWEPT', 'LUCKY', 'PRIZE', 'STOVE', 'TUBES', 'ACRES', 'WOUND', 'STEEP', 'SLIDE', 'TRUNK', 'ERROR', 'PORCH', 'SLAVE', 'EXIST', 'FACED', 'MINES', 'MARRY', 'JUICE', 'RACED', 'WAVED', 'GOOSE', 'TRUST', 'FEWER', 'FAVOR', 'MILLS', 'VIEWS', 'JOINT', 'EAGER',
'SPOTS', 'BLEND', 'RINGS', 'ADULT', 'INDEX', 'NAILS', 'HORNS', 'BALLS', 'FLAME', 'RATES', 'DRILL', 'TRACE', 'SKINS', 'WAXED', 'SEATS', 'STUFF', 'RATIO', 'MINDS', 'DIRTY', 'SILLY', 'COINS', 'HELLO', 'TRIPS', 'LEADS', 'RIFLE', 'HOPES', 'BASES', 'SHINE', 'BENCH',
'MORAL', 'FIRES', 'MEALS', 'SHAKE', 'SHOPS', 'CYCLE', 'MOVIE', 'SLOPE', 'CANOE', 'TEAMS', 'FOLKS', 'FIRED', 'BANDS', 'THUMB', 'SHOUT', 'CANAL', 'HABIT', 'REPLY', 'RULED', 'FEVER', 'CRUST', 'SHELF', 'WALKS', 'MIDST', 'CRACK', 'PRINT', 'TALES', 'COACH', 'STIFF',
'FLOOD', 'VERSE', 'AWAKE', 'ROCKY', 'MARCH', 'FAULT', 'SWIFT', 'FAINT', 'CIVIL', 'GHOST', 'FEAST', 'BLADE', 'LIMIT', 'GERMS', 'READS', 'DUCKS', 'DAIRY', 'WORST', 'GIFTS', 'LISTS', 'STOPS', 'RAPID', 'BRICK', 'CLAWS', 'BEADS', 'BEAST', 'SKIRT', 'CAKES', 'LIONS',
'FROGS', 'TRIES', 'NERVE', 'GRAND', 'ARMED', 'TREAT', 'HONEY', 'MOIST', 'LEGAL', 'PENNY', 'CROWN', 'SHOCK', 'TAXES', 'SIXTY', 'ALTAR', 'PULLS', 'SPORT', 'DRUMS', 'TALKS', 'DYING', 'DATES', 'DRANK', 'BLOWS', 'LEVER', 'WAGES', 'PROOF', 'DRUGS', 'TANKS', 'SINGS',
'TAILS', 'PAUSE', 'HERDS', 'AROSE', 'HATED', 'CLUES', 'NOVEL', 'SHAME', 'BURNT', 'RACES', 'FLASH', 'WEARY', 'HEELS', 'TOKEN', 'COATS', 'SPARE', 'SHINY', 'ALARM', 'DIMES', 'SIXTH', 'CLERK', 'MERCY', 'SUNNY', 'GUEST', 'FLOAT', 'SHONE', 'PIPES', 'WORMS', 'BILLS',
'SWEAT', 'SUITS', 'SMART', 'UPSET', 'RAINS', 'SANDY', 'RAINY', 'PARKS', 'SADLY', 'FANCY', 'RIDER', 'UNITY', 'BUNCH', 'ROLLS', 'CRASH', 'CRAFT', 'NEWLY', 'GATES', 'HATCH', 'PATHS', 'FUNDS', 'WIDER', 'GRACE', 'GRAVE', 'TIDES', 'ADMIT', 'SHIFT', 'SAILS', 'PUPIL',
'TIGER', 'ANGEL', 'CRUEL', 'AGENT', 'DRAMA', 'URGED', 'PATCH', 'NESTS', 'VITAL', 'SWORD', 'BLAME', 'WEEDS', 'SCREW', 'VOCAL', 'BACON', 'CHALK', 'CARGO', 'CRAZY', 'ACTED', 'GOATS', 'ARISE', 'WITCH', 'LOVES', 'QUEER', 'DWELL', 'BACKS', 'ROPES', 'SHOTS', 'MERRY',
'PHONE', 'CHEEK', 'PEAKS', 'IDEAL', 'BEARD', 'EAGLE', 'CREEK', 'CRIES', 'ASHES', 'STALL', 'YIELD', 'MAYOR', 'OPENS', 'INPUT', 'FLEET', 'TOOTH', 'CUBIC', 'WIVES', 'BURNS', 'POETS', 'APRON', 'SPEAR', 'ORGAN', 'CLIFF', 'STAMP', 'PASTE', 'RURAL', 'BAKED', 'CHASE',
'SLICE', 'SLANT', 'KNOCK', 'NOISY', 'SORTS', 'STAYS', 'WIPED', 'BLOWN', 'PILED', 'CLUBS', 'CHEER', 'WIDOW', 'TWIST', 'TENTH', 'HIDES', 'COMMA', 'SWEEP', 'SPOON', 'STERN', 'CREPT', 'MAPLE', 'DEEDS', 'RIDES', 'MUDDY', 'CRIME', 'JELLY', 'RIDGE', 'DRIFT', 'DUSTY',
'DEVIL', 'TEMPO', 'HUMOR', 'SENDS', 'STEAL', 'TENTS', 'WAIST', 'ROSES', 'REIGN', 'NOBLE', 'CHEAP', 'DENSE', 'LINEN', 'GEESE', 'WOVEN', 'POSTS', 'HIRED', 'WRATH', 'SALAD', 'BOWED', 'TIRES', 'SHARK', 'BELTS', 'GRASP', 'BLAST', 'POLAR', 'FUNGI', 'TENDS', 'PEARL',
'LOADS', 'JOKES', 'VEINS', 'FROST', 'HEARS', 'LOSES', 'HOSTS', 'DIVER', 'PHASE', 'TOADS', 'ALERT', 'TASKS', 'SEAMS', 'CORAL', 'FOCUS', 'NAKED', 'PUPPY', 'JUMPS', 'SPOIL', 'QUART', 'MACRO', 'FEARS', 'FLUNG', 'SPARK', 'VIVID', 'BROOK', 'STEER', 'SPRAY', 'DECAY',
'PORTS', 'SOCKS', 'URBAN', 'GOALS', 'GRANT', 'MINUS', 'FILMS', 'TUNES', 'SHAFT', 'FIRMS', 'SKIES', 'BRIDE', 'WRECK', 'FLOCK', 'STARE', 'HOBBY', 'BONDS', 'DARED', 'FADED', 'THIEF', 'CRUDE', 'PANTS', 'FLUTE', 'VOTES', 'TONAL', 'RADAR', 'WELLS', 'SKULL', 'HAIRS',
'ARGUE', 'WEARS', 'DOLLS', 'VOTED', 'CAVES', 'CARED', 'BROOM', 'SCENT', 'PANEL', 'FAIRY', 'OLIVE', 'BENDS', 'PRISM', 'LAMPS', 'CABLE', 'PEACH', 'RUINS', 'RALLY', 'SCHWA', 'LAMBS', 'SELLS', 'COOLS', 'DRAFT', 'CHARM', 'LIMBS', 'BRAKE', 'GAZED', 'CUBES', 'DELAY',
'BEAMS', 'FETCH', 'RANKS', 'ARRAY', 'HARSH', 'CAMEL', 'VINES', 'PICKS', 'NAVAL', 'PURSE', 'RIGID', 'CRAWL', 'TOAST', 'SOILS', 'SAUCE', 'BASIN', 'PONDS', 'TWINS', 'WRIST', 'FLUID', 'POOLS', 'BRAND', 'STALK', 'ROBOT', 'REEDS', 'HOOFS', 'BUSES', 'SHEER', 'GRIEF',
'BLOOM', 'DWELT', 'MELTS', 'RISEN', 'FLAGS', 'KNELT', 'FIBER', 'ROOFS', 'FREED', 'ARMOR', 'PILES', 'AIMED', 'ALGAE', 'TWIGS', 'LEMON', 'DITCH']
    length = 5
    wordlist = {5: five_letters}.get(
        length, five_letters)
    return  random_pick(wordlist)



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
            if guesses | last | value | to_upper_case | equals[solution] | collect:
                players[player_name] += 7 - len(guesses)
    z >> L[RT.Game] | for_each[game_score]
    return list(players.items()) | map[lambda kv: {"userName": kv[0], "score": kv[1]}] | collect


#############--Game Special Logic--###############
@func(g)
def game_trace_id(z: VT.ZefRef, g: VT.Graph, **defaults):
    """
    This is encoding a game's solution in a pseudorandom string that we can decode in the frontend.
    We do this so we don't return the solution in plain text.
    """
    import random
    solution = z >> RT.Solution | value | collect
    solution = (solution.upper() | enumerate
    | map[lambda i_e: str(ord(i_e[1]) + i_e[0]) + str(random.randint(11,99))]
    | join[""]
    | collect
    )
    return solution

@func(g)
def game_solution(z: VT.ZefRef, g: VT.Graph, **defaults):
    """
    For the actual solution field of game, we return a random "Wrong" answer, just to confuse cheaters ;)
    """
    return random_pick(["WRONG", "LOSER", "CHEAT"])
#############--User Special Logic--###############
@func(g)
def user_duels(z: VT.ZefRef, g: VT.Graph, **defaults):
    filter_days = 7
    return z << L[RT.Participant] | filter[lambda d: now() - time(d >> L[RT.Game] | last | instantiated) < (now() - Time(f"{filter_days} days"))] | collect
#----------------------------------------------------------------



# Retrieve the schema root and also the GQL_Types
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
       return ('''
                if type(z) == dict: return z["id"]
                else: return str(z | to_ezefref | uid | collect)''',
    ["z", "ctx"])
    return ("return None #This means that no resolver is defined!", ["z", "ctx"])
""") | collect
(schema, RT.CustomerSpecificResolvers, specific_resolvers) | g | run
#----------------------------------------------------------------


# Connecting the delegate and zef function resolvers for each type
# Some types have a mix of the two to resolve their types


# Mutations Handlers
def get_zefref_for_func(x):
  return LazyValue(x) | absorbed | first | second | collect


mutations_dict = {
    "acceptDuel":   get_zefref_for_func(accept_duel),
    "createUser":   get_zefref_for_func(create_user),
    "createDuel":   get_zefref_for_func(create_duel),
    "createGame":   get_zefref_for_func(create_game),
    "submitGuess":  get_zefref_for_func(submit_guess),
}
connect_zef_function_resolvers(g, types['GQL_Mutation'], mutations_dict)


# Query Handlers
query_dict = {
    "getUser":          get_zefref_for_func(get_user),
    "getGame":          get_zefref_for_func(get_game),
    "getDuel":          get_zefref_for_func(get_duel),
    "getRandomWord":    get_zefref_for_func(get_random_word),
}
connect_zef_function_resolvers(g, types['GQL_Query'], query_dict)


# User Handlers
user_dict = {
    "name":  {"triple": (ET.User, RT.Name, AET.String)},
}
connect_delegate_resolvers(g, types['GQL_User'], user_dict)
user_dict = {
    "duels":       get_zefref_for_func(user_duels),
}
connect_zef_function_resolvers(g, types['GQL_User'], user_dict)


# Duel Handlers
duel_dict = {
    "games":   {"triple": (ET.Duel, RT.Game, ET.Game)},
    "players": {"triple": (ET.Duel, RT.Participant, ET.User)},
}
connect_delegate_resolvers(g, types['GQL_Duel'], duel_dict)
duel_dict = {
    "currentGame":      get_zefref_for_func(duel_current_game),
    "currentScore":     get_zefref_for_func(duel_current_score),

}
connect_zef_function_resolvers(g, types['GQL_Duel'], duel_dict)

# Game Handlers
game_dict = {
    "player":       {"triple": (ET.Game, RT.Player, ET.User)},
    "creator":      {"triple": (ET.Game, RT.Creator, ET.User)},
    "duel":         {"triple": (ET.Duel, RT.Game, ET.Game), "is_out": False},  # is_out is True by default, setting it to False means that the traversal is in traversal and the direction of resolving is shifted.
    "guesses":      {"triple": (ET.Game, RT.Guess, AET.String)},
    "completed":    {"triple": (ET.Game, RT.Completed, AET.Bool)},
}
connect_delegate_resolvers(g, types['GQL_Game'], game_dict)
game_dict = {
    "solution":    get_zefref_for_func(game_solution),
    "traceID":     get_zefref_for_func(game_trace_id),
}
connect_zef_function_resolvers(g, types['GQL_Game'], game_dict)



# Sync and tag the graph so it could be run on a different process/server
wordle_tag = os.getenv("TAG", "worduel/main3")
g | sync[True] | run
g | tag[wordle_tag] | run