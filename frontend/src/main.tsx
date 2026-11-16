import React from 'react'
import { createRoot } from 'react-dom/client'
import '@fortawesome/fontawesome-free/css/fontawesome.min.css'
import '@fortawesome/fontawesome-free/css/solid.min.css'
import './design/tokens.css'
import './styles.css'
import './shell/kit.css'
import './shell/shell.css'
import { App } from './App'
import { initMobileClass } from './shell/sidePref'
import './kit/sheet.css'
import './shell/mobile.css'
initMobileClass()
createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>)
