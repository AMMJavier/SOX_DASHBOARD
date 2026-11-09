import AppRouter from "./routes/router";
import SessionTimeout from "./components/auth/SessionTimeout";

export default function App() {
  return (
    <>
      <SessionTimeout />
      <AppRouter />
    </>
  );
}