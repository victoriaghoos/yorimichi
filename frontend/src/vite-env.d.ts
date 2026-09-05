/// <reference types="vite/client" />
/// <reference types="vite-plugin-pwa/client" />

interface ImportMetaEnv {
	readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
	readonly env: ImportMetaEnv
}

declare module '*.css'

declare module '*.png' {
	const src: string
	export default src
}