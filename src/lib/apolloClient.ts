import { ApolloClient, InMemoryCache } from "@apollo/client";

const client = new ApolloClient({
  uri: "http://localhost:5010/gql",
  cache: new InMemoryCache(),
});

export default client;
