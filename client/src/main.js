import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import App from './App.vue'
import Home from './views/Home.vue'
import DataHealth from './views/DataHealth.vue'
import QuoteJourney from './views/QuoteJourney.vue'
import Policies from './views/Policies.vue'
import Policy from './views/Policy.vue'
import './styles/base.css'

// Hash routing, so the app works behind the sandbox's dynamic proxy prefix.
const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', component: Home },
    { path: '/data', component: DataHealth },
    { path: '/quote', component: QuoteJourney },
    { path: '/policies', component: Policies },
    { path: '/policies/:ref', component: Policy }
  ]
})

const app = createApp(App)
app.use(router)
app.mount('#app')
