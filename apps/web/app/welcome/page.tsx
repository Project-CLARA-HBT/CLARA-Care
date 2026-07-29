import { redirect } from "next/navigation";

export default function WelcomeIndexPage() {
  redirect("/welcome/start");
}
