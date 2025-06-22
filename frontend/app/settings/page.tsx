'use client'

import React, { useState } from 'react'
import Sidebar from '../components/Sidebar'
import { useSettingsStore, GeoServerBackend, SearchPortal } from '../stores/settingsStore'

export default function SettingsPage() {
    const portals = useSettingsStore((s) => s.search_portals)
    const addPortal = useSettingsStore((s) => s.addPortal)
    const removePortal = useSettingsStore((s) => s.removePortal)
    const togglePortal = useSettingsStore((s) => s.togglePortal)
    const backends = useSettingsStore((s) => s.geoserver_backends)
    const addBackend = useSettingsStore((s) => s.addBackend)
    const removeBackend = useSettingsStore((s) => s.removeBackend)
    const toggleBackend = useSettingsStore((s) => s.toggleBackend)

    const [newPortal, setNewPortal] = useState('')
    const [newBackend, setNewBackend] = useState<Omit<GeoServerBackend, 'enabled'>>({ url: '', username: '', password: '' })

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
                    <ul className="space-y-2">
                        {portals.map((p, i) => (
                            <li key={i} className="flex justify-between items-center">
                                <label className="flex items-center space-x-3">
                                    <input
                                        type="checkbox"
                                        checked={p.enabled}
                                        onChange={() => togglePortal(p.url)}
                                        className="form-checkbox h-5 w-5 text-green-600"
                                    />
                                    <span className={`${p.enabled ? 'text-gray-900' : 'text-gray-400'}`}>{p.url}</span>
                                </label>
                                <button onClick={() => removePortal(p.url)} className="text-red-600 hover:underline">
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
                                <label className="flex items-center space-x-3">
                                    <input
                                        type="checkbox"
                                        checked={b.enabled}
                                        onChange={() => toggleBackend(b.url)}
                                        className="form-checkbox h-5 w-5 text-green-600"
                                    />
                                    <div>
                                        <p className={`${b.enabled ? 'text-gray-900' : 'text-gray-400'}`}><strong>URL:</strong> {b.url}</p>
                                        {b.username && <p className={`${b.enabled ? 'text-gray-900' : 'text-gray-400'}`}><strong>Username:</strong> {b.username}</p>}
                                    </div>
                                </label>
                                <button onClick={() => removeBackend(b.url)} className="text-red-600 hover:underline">
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
