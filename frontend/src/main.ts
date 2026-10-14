import { createApp } from "vue";
import App from "./App.vue";
import CarClient from "./CarClient.vue";
import PhoneClient from "./PhoneClient.vue";
import "./style.css";

const path = window.location.pathname.replace(/\/$/, "");
const RootComponent = path === "/phone" ? PhoneClient : path === "/car" ? CarClient : App;

createApp(RootComponent).mount("#app");
