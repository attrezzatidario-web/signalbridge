import { useEffect, useState } from 'react'
import { Activity, Radio, Users, History as HistoryIcon, Settings as Cog } from 'lucide-react'
import { isLogged, setUnauthorizedHandler } from './lib/api'
import Login from './pages/Login'
import Home from './pages/Home'
import Signals from './pages/Signals'
import Groups from './pages/Groups'
import History from './pages/History'
import Settings from './pages/Settings'

const TABS = [
  ['home', 'Home', Activity, Home],
  ['signals', 'Segnali', Radio, Signals],
  ['groups', 'Gruppi', Users, Groups],
  ['history', 'Storico', HistoryIcon, History],
  ['settings', 'Impostazioni', Cog, Settings],
]

export default function App() {
  const [logged, setLogged] = useState(undefined)
  const [tab, setTab] = useState(() => localStorage.getItem('sb_tab') || 'home')

  useEffect(() => {
    setUnauthorizedHandler(() => setLogged(false))
    isLogged().then(setLogged)
  }, [])
  useEffect(() => { localStorage.setItem('sb_tab', tab) }, [tab])

  if (logged === undefined) return null
  if (!logged) return <Login onDone={() => setLogged(true)} />

  const Page = (TABS.find(t => t[0] === tab) || TABS[0])[3]

  return (
    <div className="min-h-full md:flex">
      {/* sidebar desktop */}
      <aside className="hidden md:flex md:flex-col w-56 shrink-0 border-r border-line p-4 gap-1 sticky top-0 h-screen">
        <div className="flex items-center gap-2 px-2 pb-6 pt-1">
          <img src={import.meta.env.BASE_URL + "icon.svg"} className="w-7 h-7" alt="" />
          <span className="font-semibold">SignalBridge</span>
        </div>
        {TABS.map(([id, label, Icon]) => (
          <button key={id} onClick={() => setTab(id)}
            className={`flex items-center gap-3 px-3 py-2 rounded-xl text-sm transition ${tab === id ? 'bg-card text-white' : 'text-mute hover:text-zinc-200'}`}>
            <Icon size={18} />{label}
          </button>
        ))}
      </aside>

      <main className="flex-1 min-w-0 safe-t pb-24 md:pb-8">
        <div className="max-w-3xl mx-auto px-4 pt-5"><Page goto={setTab} /></div>
      </main>

      {/* tab bar mobile */}
      <nav className="md:hidden fixed bottom-0 inset-x-0 z-40 bg-bg/95 backdrop-blur border-t border-line safe-b">
        <div className="grid grid-cols-5">
          {TABS.map(([id, label, Icon]) => (
            <button key={id} onClick={() => setTab(id)}
              className={`flex flex-col items-center gap-1 pt-2.5 pb-1 text-[10px] ${tab === id ? 'text-white' : 'text-mute'}`}>
              <Icon size={20} strokeWidth={tab === id ? 2.2 : 1.8} />{label}
            </button>
          ))}
        </div>
      </nav>
    </div>
  )
}
