# Copyright (c) 2022 Synchronous Technologies Pte Ltd
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

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
 traceID:   String
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
  userInfo: User
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
