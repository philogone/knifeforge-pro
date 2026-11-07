import { createPinia } from "pinia";
import { createApp } from "vue";

import App from "@/App.vue";
import { initTheme } from "@/composables/useTheme";
import router from "@/router";

import "@fontsource/ibm-plex-sans/latin-400.css";
import "@fontsource/ibm-plex-sans/latin-500.css";
import "@fontsource/ibm-plex-sans/latin-600.css";
import "@fontsource/ibm-plex-mono/latin-400.css";
import "@fontsource/ibm-plex-mono/latin-500.css";
import "@/assets/main.css";

initTheme();
const app = createApp(App);
app.use(createPinia());
app.use(router);
app.mount("#app");
