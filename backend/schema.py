schema_gql = """
type Query {
  getUser(userId: ID): User
  getGame(gameId: ID): Game
  getDuel(duelId: ID): Duel
  getRandomWord(length: Int): String
}

type Mutation {
    acceptDuel(duelId: ID, playerId: ID): ID
    createUser(name: String): ID
    createDuel(creatorId: ID): ID 
    createGame(solution: String, duelId: ID, creatorId: ID): CreateGameReturnType 
    submitGuess(gameId: ID, guess: String): SubmitGuessReturnType
}

type User {
 id: ID
 name: String
 duels: [Duel]
}

type Game {
 id: ID
 creator: User
 player: User
 duel: Duel
 completed: Boolean
 solution:  String
 guesses: [String]
}

type Duel {
 id: ID
 players: [User]
 games:   [Game]
 currentGame: Game
 currentScore: [Score]
}

type Score {
  userName: String
  score: Int
}

type SubmitGuessReturnType {
  isEligibleGuess:  Boolean
  solved:           Boolean
  failed:           Boolean
  guessResult:      [String]
  discardedLetters: [String]
  message:          String
}

type CreateGameReturnType {
  success: Boolean
  message: String
  id:      ID  
}

scalar ID
scalar Datetime
"""
