'use client'

import React, { useState } from 'react'
import Sidebar from '../components/Sidebar'
import { useSettingsStore, GeoServerBackend } from '../stores/settingsStore'

export default function SettingsPage() {
    const portals = useSettingsStore((s) => s.search_portals)
    const addPortal = useSettingsStore((s) => s.addPortal)
    const removePortal = useSettingsStore((s) => s.removePortal)
    const backends = useSettingsStore((s) => s.geoserver_backends)
    const addBackend = useSettingsStore((s) => s.addBackend)
    const removeBackend = useSettingsStore((s) => s.removeBackend)

    const [newPortal, setNewPortal] = useState('')
    const [newBackend, setNewBackend] = useState<GeoServerBackend>({ url: '', username: '', password: '' })

    return (
        <div className="relative h-screen w-screen overflow-hidden">
            <div className="fixed left-0 top-0 bottom-0 w-[4%] z-[2]" style={{ backgroundColor: 'rgb(64, 64, 64)' }}>
                <Sidebar />
            </div>
            <main className="fixed top-0 left-[10%] right-[10%] bottom-0 w-[80%] overflow-auto scroll-smooth">
                <h1 className="text-3xl font-semibold mb-6">Settings</h1>

                {/* Geodata Portals */}
                <section className="mb-8">
                    <h2 className="text-2xl mb-4">Geodata Portals</h2>
                    <div className="flex space-x-2 mb-4">
                        <input
                            value={newPortal}
                            onChange={(e) => setNewPortal(e.target.value)}
                            placeholder="Portal URL"
                            className="border rounded p-2 flex-grow"
                        />
                        <button
                            onClick={() => { addPortal(newPortal.trim()); setNewPortal('') }}
                            className="bg-blue-600 text-white px-4 py-2 rounded"
                        >
                            Add
                        </button>
                    </div>
                    <ul className="list-disc list-inside space-y-2">
                        {portals.map((url, i) => (
                            <li key={i} className="flex justify-between">
                                <span>{url}</span>
                                <button onClick={() => removePortal(url)} className="text-red-600 hover:underline">
                                    Remove
                                </button>
                            </li>
                        ))}
                    </ul>
                </section>

                {/* GeoServer Backends */}
                <section>
                    <h2 className="text-2xl mb-4">GeoServer Backends</h2>
                    <div className="space-y-3 mb-4">
                        <input
                            value={newBackend.url}
                            onChange={(e) => setNewBackend({ ...newBackend, url: e.target.value })}
                            placeholder="GeoServer URL"
                            className="border rounded p-2 w-full"
                        />
                        <input
                            value={newBackend.username}
                            onChange={(e) => setNewBackend({ ...newBackend, username: e.target.value })}
                            placeholder="Username (optional)"
                            className="border rounded p-2 w-full"
                        />
                        <input
                            type="password"
                            value={newBackend.password}
                            onChange={(e) => setNewBackend({ ...newBackend, password: e.target.value })}
                            placeholder="Password (optional)"
                            className="border rounded p-2 w-full"
                        />
                        <button
                            onClick={() => { addBackend(newBackend); setNewBackend({ url: '', username: '', password: '' }) }}
                            className="bg-blue-600 text-white px-4 py-2 rounded"
                        >
                            Add Backend
                        </button>
                    </div>
                    <ul className="space-y-3">
                        {backends.map((b, i) => (
                            <li key={i} className="border rounded p-4 flex justify-between items-center">
                                <div>
                                    <p><strong>URL:</strong> {b.url}</p>
                                    {b.username && <p><strong>Username:</strong> {b.username}</p>}
                                </div>
                                <button onClick={() => removeBackend(b)} className="text-red-600 hover:underline">
                                    Remove
                                </button>
                            </li>
                        ))}
                    </ul>
                </section>
            </main>
        </div>
    )
}
