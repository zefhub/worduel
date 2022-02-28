import React from "react";
import { useForm } from "react-hook-form";
import { gql, useMutation } from "@apollo/client";
import toast from "react-hot-toast";
import { v4 as uuidv4 } from "uuid";
import WelcomeBanner from "components/WelcomeBanner";
import Footer from "components/Footer";

const CREATE_USER = gql`
  mutation createUser($name: String!) {
    createUser(name: $name) {
      id
    }
  }
`;

export interface UsernameProps {
  setScene: (screen: string) => void;
}

const Username: React.FC<UsernameProps> = (props) => {
  const { register, handleSubmit } = useForm();
  const [createUser, { loading, error }] = useMutation(CREATE_USER);

  if (error) {
    toast.error(error.message);
  }

  const onSubmit = async (values: any) => {
    if (values.username) {
      const user = await createUser({ variables: { name: values.username } });
      console.log("user", user);
      // Generate id and save to local storage
      window.localStorage.setItem(
        "user",
        JSON.stringify({ id: uuidv4(), username: values.username })
      );
      props.setScene("CREATE_DUEL");
    }
  };

  return (
    <div>
      <WelcomeBanner />
      <div className="flex justify-center mb-12">
        <div className="w-30 card">
          <form onSubmit={handleSubmit(onSubmit)}>
            <label
              htmlFor="username"
              className="text-lg flex justify-center mb-3"
            >
              Enter your name:
            </label>
            <input
              {...register("username", { required: true })}
              id="username"
              type="text"
              className="block bg-white w-full border border-slate-300 rounded-md py-3 pl-3 pr-3 shadow-sm focus:outline-none focus:border-sky-500 focus:ring-sky-500 focus:ring-1 sm:text-sm mb-3"
              placeholder="John Doe"
              required
              disabled={loading}
            />
            <div className="flex justify-center">
              <button
                type="submit"
                className="bg-black text-white py-3 pl-6 pr-6 shadow-sm rounded-md"
                disabled={loading}
              >
                Submit
              </button>
            </div>
          </form>
        </div>
      </div>
      <Footer />
    </div>
  );
};

export default Username;
