'use client'

import React, { useState, useEffect } from 'react'
import Sidebar from '../components/sidebar/Sidebar'
import {
    useSettingsStore,
    GeoServerBackend
} from '../stores/settingsStore'

export default function SettingsPage() {
    // settings
    const portals = useSettingsStore((s) => s.search_portals)
    const addPortal = useSettingsStore((s) => s.addPortal)
    const removePortal = useSettingsStore((s) => s.removePortal)
    const togglePortal = useSettingsStore((s) => s.togglePortal)
    const backends = useSettingsStore((s) => s.geoserver_backends)
    const addBackend = useSettingsStore((s) => s.addBackend)
    const removeBackend = useSettingsStore((s) => s.removeBackend)
    const toggleBackend = useSettingsStore((s) => s.toggleBackend)
    const modelSettings = useSettingsStore((s) => s.model_settings)
    const setModelProvider = useSettingsStore((s) => s.setModelProvider)
    const setModelName = useSettingsStore((s) => s.setModelName)
    const setMaxTokens = useSettingsStore((s) => s.setMaxTokens)
    const setSystemPrompt = useSettingsStore((s) => s.setSystemPrompt)
    const tools = useSettingsStore((s) => s.tools)
    const addToolConfig = useSettingsStore((s) => s.addToolConfig)
    const removeToolConfig = useSettingsStore((s) => s.removeToolConfig)
    const toggleToolConfig = useSettingsStore((s) => s.toggleToolConfig)
    const setToolPromptOverride = useSettingsStore((s) => s.setToolPromptOverride)
    const setAvailableTools = useSettingsStore((s) => s.setAvailableTools)
    const setAvailableSearchPortals = useSettingsStore((s) => s.setAvailableSearchPortals)
    const setAvailableModelProviders = useSettingsStore((s) => s.setAvailableModelProviders)
    const setAvailableModelNames = useSettingsStore((s) => s.setAvailableModelNames)

    // available options
    const availableTools = useSettingsStore((s) => s.available_tools)
    const availablePortals = useSettingsStore((s) => s.available_search_portals)
    const availableProviders = useSettingsStore((s) => s.available_model_providers)
    const availableModelNames = useSettingsStore((s) => s.available_model_names)

    // local state
    const [newPortal, setNewPortal] = useState('')
    const [newBackend, setNewBackend] = useState<Omit<GeoServerBackend, 'enabled'>>({ url: '', username: '', password: '' })
    const [newToolName, setNewToolName] = useState('')

    // mock load available options (replace with real API calls)
    useEffect(() => {
        setAvailableTools(['search', 'geocode', 'analyze'])
        setAvailableSearchPortals(['FAO', 'MapX'])
        setAvailableModelProviders(['openai'])
        setAvailableModelNames(['gpt-4-nano', 'gpt-3-mini'])
    }, [])

    return (
        <div className="relative h-screen w-screen overflow-hidden">
            <div className="fixed left-0 top-0 bottom-0 w-[4%] bg-gray-800">
                <Sidebar />
            </div>
            <main className="fixed top-0 left-[10%] right-[10%] bottom-0 w-[80%] overflow-auto p-6 space-y-8 scroll-smooth">
                <h1 className="text-3xl font-semibold">Settings</h1>

                {/* Model Settings */}
                <section className="space-y-4">
                    <h2 className="text-2xl">Model Settings</h2>
                    <div className="grid grid-cols-2 gap-4">
                        <select
                            value={modelSettings.model_provider}
                            onChange={(e) => setModelProvider(e.target.value)}
                            className="border rounded p-2"
                        >
                            {availableProviders.map((prov) => (
                                <option key={prov} value={prov}>{prov}</option>
                            ))}
                        </select>
                        <select
                            value={modelSettings.model_name}
                            onChange={(e) => setModelName(e.target.value)}
                            className="border rounded p-2"
                        >
                            {availableModelNames.map((name) => (
                                <option key={name} value={name}>{name}</option>
                            ))}
                        </select>
                        <input
                            type="number"
                            value={modelSettings.max_tokens}
                            onChange={(e) => setMaxTokens(Number(e.target.value))}
                            placeholder="Max Tokens"
                            className="border rounded p-2"
                        />
                        <textarea
                            value={modelSettings.system_prompt}
                            onChange={(e) => setSystemPrompt(e.target.value)}
                            placeholder="System Prompt"
                            className="border rounded p-2 col-span-2 h-24"
                        />
                    </div>
                </section>

                {/* Tools Configuration */}
                <section className="space-y-4">
                    <h2 className="text-2xl">Tools Configuration</h2>
                    <div className="flex space-x-2 mb-4">
                        <select
                            value={newToolName}
                            onChange={(e) => setNewToolName(e.target.value)}
                            className="border rounded p-2 flex-grow"
                        >
                            <option value="">Select tool to add</option>
                            {availableTools.map((tool) => (
                                <option key={tool} value={tool}>{tool}</option>
                            ))}
                        </select>
                        <button
                            onClick={() => { newToolName && addToolConfig(newToolName); setNewToolName('') }}
                            className="bg-blue-600 text-white px-4 py-2 rounded"
                        >
                            Add Tool
                        </button>
                    </div>
                    <ul className="space-y-3">
                        {tools.map((t, i) => (
                            <li key={i} className="border rounded p-4 space-y-2">
                                <div className="flex justify-between items-center">
                                    <label className="flex items-center space-x-2">
                                        <input
                                            type="checkbox"
                                            checked={t.enabled}
                                            onChange={() => toggleToolConfig(t.name)}
                                            className="form-checkbox h-5 w-5 text-green-600"
                                        />
                                        <span className={`${t.enabled ? 'text-gray-900' : 'text-gray-400'}`}>{t.name}</span>
                                    </label>
                                    <button onClick={() => removeToolConfig(t.name)} className="text-red-600 hover:underline">
                                        Remove
                                    </button>
                                </div>
                                <textarea
                                    value={t.prompt_override}
                                    onChange={(e) => setToolPromptOverride(t.name, e.target.value)}
                                    placeholder="Prompt Override"
                                    className="border rounded p-2 w-full h-20"
                                />
                            </li>
                        ))}
                    </ul>
                </section>

                {/* Geodata Portals */}
                <section className="space-y-4">
                    <h2 className="text-2xl">Geodata Portals</h2>
                    <div className="flex space-x-2 mb-4">
                        <select
                            value={newPortal}
                            onChange={(e) => setNewPortal(e.target.value)}
                            className="border rounded p-2 flex-grow"
                        >
                            <option value="">Select portal to add</option>
                            {availablePortals.map((portal) => (
                                <option key={portal} value={portal}>{portal}</option>
                            ))}
                        </select>
                        <button
                            onClick={() => { newPortal && addPortal(newPortal); setNewPortal('') }}
                            className="bg-blue-600 text-white px-4 py-2 rounded"
                        >
                            Add Portal
                        </button>
                    </div>
                    <ul className="space-y-3">
                        {portals.map((p, i) => (
                            <li key={i} className="flex justify-between items-center border rounded p-4">
                                <label className="flex items-center space-x-2">
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
                <section className="space-y-4">
                    <h2 className="text-2xl">GeoServer Backends</h2>
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
                            <li key={i} className="flex justify-between items-center border rounded p-4">
                                <label className="flex items-center space-x-2">
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
