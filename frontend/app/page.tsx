// app/page.tsx
import Sidebar from './components/Sidebar'
import MapWithChat from './components/MapWithChat'

export default function Home() {
  return (
    <div className="flex h-screen">
      {/* Sidebar on the left */}
      <Sidebar />
      {/* Main area for the map with chat overlay */}
      <div className="flex-1">
        <MapWithChat />
      </div>
    </div>
  )
}
