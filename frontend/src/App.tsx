import { useEffect, useRef, useState } from 'react'
import { motion, useInView } from 'framer-motion'
import {
  Activity, AlertCircle, ArrowUpRight, BarChart3,
  Car, CheckCircle2, ChevronRight, Clock, CloudLightning, Code2,
  Cpu, Database, ExternalLink, GitBranch, Globe, Layers,
  Map, Menu, Navigation,
  Server, Shield, Terminal, X, Zap
} from 'lucide-react'

const FadeIn = ({ children, delay = 0, direction = 'up' }: { children: React.ReactNode; delay?: number; direction?: 'up' | 'left' | 'right' | 'none' }) => {
  const ref = useRef(null)
  const inView = useInView(ref, { once: true, margin: '-80px' })
  const yInit = direction === 'up' ? 40 : 0
  const xInit = direction === 'left' ? -40 : direction === 'right' ? 40 : 0
  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: yInit, x: xInit }}
      animate={inView ? { opacity: 1, y: 0, x: 0 } : {}}
      transition={{ duration: 0.8, delay, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  )
}

function Navbar() {
  const [scrolled, setScrolled] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 60)
    window.addEventListener('scroll', onScroll)
    return () => window.removeEventListener('scroll', onScroll)
  }, [])
  const navLinks = ['Platform', 'Services', 'API', 'About']
  return (
    <>
      <motion.header
        className="fixed top-5 left-0 right-0 z-50 flex justify-center px-4"
        initial={{ y: -80, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
      >
        <nav
          className="w-full max-w-5xl flex items-center justify-between px-6 py-3 rounded-full transition-all duration-500"
          style={{
            background: scrolled ? 'rgba(5, 8, 16, 0.92)' : 'rgba(5, 8, 16, 0.35)',
            backdropFilter: 'blur(16px)',
            border: scrolled ? '1px solid rgba(59, 130, 246, 0.18)' : '1px solid rgba(255,255,255,0.06)',
          }}
        >
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #3b82f6, #06b6d4)' }}>
              <Navigation className="w-4 h-4 text-white" />
            </div>
            <span className="font-bold text-lg tracking-tight" style={{ color: '#f2f2f2' }}>
              Smart<span style={{ color: '#3b82f6' }}>Toll</span>
            </span>
          </div>
          <div className="hidden md:flex items-center gap-1">
            {navLinks.map(link => (
              <a key={link} href={`#${link.toLowerCase()}`}
                className="px-4 py-2 text-sm rounded-full transition-all duration-200 hover:bg-white/5"
                style={{ color: 'rgba(242,242,242,0.7)' }}>{link}</a>
            ))}
          </div>
          <div className="hidden md:flex items-center gap-3">
            <a href="http://localhost:8001/docs" target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-2 px-5 py-2 text-sm font-semibold rounded-full"
              style={{ background: 'linear-gradient(135deg, #3b82f6, #06b6d4)', color: 'white' }}>
              View API Docs
              <div className="w-4 h-4 bg-white/20 rounded-full flex items-center justify-center">
                <ArrowUpRight className="w-2.5 h-2.5" />
              </div>
            </a>
          </div>
          <button className="md:hidden text-white/70 hover:text-white" onClick={() => setMenuOpen(!menuOpen)}>
            {menuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </nav>
      </motion.header>
      {menuOpen && (
        <motion.div className="fixed inset-0 z-40 flex flex-col items-center justify-center gap-6"
          style={{ background: 'rgba(5, 8, 16, 0.97)', backdropFilter: 'blur(20px)' }}
          initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          {navLinks.map((link, i) => (
            <motion.a key={link} href={`#${link.toLowerCase()}`}
              className="text-2xl font-semibold text-white/80 hover:text-white"
              initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1 }} onClick={() => setMenuOpen(false)}>{link}</motion.a>
          ))}
          <motion.a href="http://localhost:8001/docs" target="_blank" rel="noopener noreferrer"
            className="btn-primary px-8 py-3 text-sm mt-4"
            initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}>
            View API Docs
          </motion.a>
        </motion.div>
      )}
    </>
  )
}

const PIPELINE_STEPS = [
  { step: '01', label: 'GPS Ingestion', value: 'lat=40.714, lon=-74.006', color: '#3b82f6', icon: <Navigation className="w-3.5 h-3.5" /> },
  { step: '02', label: 'Zone Detection', value: 'Zone1 ENTERED ✓', color: '#06b6d4', icon: <Map className="w-3.5 h-3.5" /> },
  { step: '03', label: 'Toll Calculated', value: '$2.50 · 0.82 km', color: '#22c55e', icon: <Zap className="w-3.5 h-3.5" /> },
  { step: '04', label: 'Payment Processed', value: 'TXN-8821 · SUCCESS', color: '#8b5cf6', icon: <CheckCircle2 className="w-3.5 h-3.5" /> },
]

function Hero() {
  const pipeline = PIPELINE_STEPS
  return (
    <section className="relative min-h-[92vh] flex flex-col justify-center overflow-hidden pt-20" style={{ background: '#050810' }}>
      {/* Background radial glows */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[800px] h-[800px] rounded-full"
          style={{ background: 'radial-gradient(circle, rgba(59,130,246,0.08) 0%, transparent 70%)' }} />
        <div className="absolute top-1/3 left-1/3 w-[400px] h-[400px] rounded-full"
          style={{ background: 'radial-gradient(circle, rgba(6,182,212,0.05) 0%, transparent 70%)' }} />
      </div>
      {/* Grid */}
      <div className="absolute inset-0 pointer-events-none opacity-20"
        style={{
          backgroundImage: `linear-gradient(rgba(59,130,246,0.15) 1px, transparent 1px), linear-gradient(90deg, rgba(59,130,246,0.15) 1px, transparent 1px)`,
          backgroundSize: '60px 60px'
        }} />

      {/* Pipeline flow visualization — right side */}
      <div className="hidden lg:flex flex-col gap-2 absolute right-10 xl:right-20 top-1/2 -translate-y-1/2 z-10">
        {pipeline.map((item, i) => (
          <div key={item.step}>
            <motion.div
              initial={{ opacity: 0, x: 30 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.6 + i * 0.18, duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
              className="card-glass rounded-xl px-4 py-3 flex items-center gap-3"
              style={{ minWidth: '240px', borderLeft: `2px solid ${item.color}` }}
            >
              <div className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0"
                style={{ background: `${item.color}20`, color: item.color, fontFamily: 'monospace' }}>
                {item.step}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-semibold text-white mb-0.5">{item.label}</p>
                <p className="text-xs font-mono truncate" style={{ color: item.color }}>{item.value}</p>
              </div>
              <span style={{ color: item.color }}>{item.icon}</span>
            </motion.div>
            {i < pipeline.length - 1 && (
              <div className="flex justify-center my-1">
                <motion.div
                  className="w-px bg-gradient-to-b from-white/10 to-transparent"
                  style={{ height: '16px' }}
                  initial={{ scaleY: 0 }} animate={{ scaleY: 1 }}
                  transition={{ delay: 0.7 + i * 0.18, duration: 0.4 }}
                />
              </div>
            )}
          </div>
        ))}
        <motion.p
          className="text-center text-xs text-white/20 uppercase tracking-widest mt-2 font-mono"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1.4 }}>
          event pipeline
        </motion.p>
      </div>

      {/* Floating metric cards */}
      <motion.div className="absolute top-28 right-8 md:right-24 card-glass rounded-2xl p-4 hidden md:block lg:hidden"
        animate={{ y: [0, -8, 0] }} transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}>
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full flex items-center justify-center" style={{ background: 'rgba(59,130,246,0.2)' }}>
            <Activity className="w-4 h-4 text-blue-400" />
          </div>
          <div>
            <p className="text-xs text-white/40 font-mono">Real-time Events</p>
            <p className="text-sm font-bold text-white">12,483 / sec</p>
          </div>
        </div>
      </motion.div>
      <motion.div className="absolute top-48 right-8 md:right-16 card-glass rounded-2xl p-4 hidden md:block lg:hidden"
        animate={{ y: [0, 8, 0] }} transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut', delay: 1 }}>
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full flex items-center justify-center" style={{ background: 'rgba(6,182,212,0.2)' }}>
            <CheckCircle2 className="w-4 h-4 text-cyan-400" />
          </div>
          <div>
            <p className="text-xs text-white/40 font-mono">Payment Success</p>
            <p className="text-sm font-bold text-white">99.1%</p>
          </div>
        </div>
      </motion.div>

      {/* Main content */}
      <div className="relative z-10 section-padding">
        <div className="max-w-7xl mx-auto lg:max-w-[55%]">
          <FadeIn delay={0.1} direction="none">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs font-semibold uppercase tracking-widest mb-8"
              style={{ border: '1px solid rgba(59,130,246,0.3)', background: 'rgba(59,130,246,0.1)', color: '#60a5fa' }}>
              <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
              Production-Grade Toll Infrastructure
            </div>
          </FadeIn>
          <FadeIn delay={0.2}>
            <h1 className="text-6xl md:text-7xl lg:text-8xl font-black tracking-tighter leading-none mb-6">
              <span style={{ color: 'hsl(0,0%,95%)' }}>Intelligent</span><br />
              <span style={{ background: 'linear-gradient(135deg, #3b82f6, #06b6d4)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                Toll Processing
              </span><br />
              <span style={{ color: 'hsl(0,0%,95%)' }}>at Scale.</span>
            </h1>
          </FadeIn>
          <FadeIn delay={0.4}>
            <p className="text-lg md:text-xl text-white/50 max-w-xl mb-10 leading-relaxed">
              Real-time GPS event processing, sub-millisecond geofence detection, and automated billing — built on Kafka, PostGIS, and Redis.
            </p>
          </FadeIn>
          <FadeIn delay={0.5}>
            <div className="flex flex-wrap gap-4">
              <a href="http://localhost:8001/docs" target="_blank" rel="noopener noreferrer"
                className="btn-primary flex items-center gap-2 px-8 py-4">
                Explore API <ArrowUpRight className="w-4 h-4" />
              </a>
              <a href="#platform" className="flex items-center gap-2 px-8 py-4 rounded-full text-white/70 hover:text-white transition-all duration-300"
                style={{ border: '1px solid rgba(255,255,255,0.1)' }}>
                Learn More <ChevronRight className="w-4 h-4" />
              </a>
            </div>
          </FadeIn>
        </div>
      </div>
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2">
        <motion.div animate={{ y: [0, 8, 0] }} transition={{ duration: 1.5, repeat: Infinity }}
          className="flex flex-col items-center gap-2 text-white/30 text-xs">
          <div className="w-5 h-8 rounded-full border border-white/20 flex items-start justify-center pt-1.5">
            <div className="w-1 h-2 bg-white/40 rounded-full" />
          </div>
        </motion.div>
      </div>
    </section>
  )
}

function MarqueeBar() {
  const items = [
    { icon: <Zap className="w-3.5 h-3.5" />, text: '< 5ms GPS Processing Latency' },
    { icon: <Shield className="w-3.5 h-3.5" />, text: 'PostGIS Spatial Geofencing' },
    { icon: <Activity className="w-3.5 h-3.5" />, text: 'Kafka Event Streaming' },
    { icon: <Database className="w-3.5 h-3.5" />, text: 'Redis State Management' },
    { icon: <CheckCircle2 className="w-3.5 h-3.5" />, text: 'Idempotent Transactions' },
    { icon: <BarChart3 className="w-3.5 h-3.5" />, text: 'Prometheus Observability' },
  ]
  const doubled = [...items, ...items]
  return (
    <div className="overflow-hidden py-3" style={{ background: 'rgba(59,130,246,0.08)', borderTop: '1px solid rgba(59,130,246,0.15)', borderBottom: '1px solid rgba(59,130,246,0.15)' }}>
      <div className="flex animate-marquee" style={{ width: 'max-content' }}>
        {doubled.map((item, i) => (
          <div key={i} className="flex items-center gap-2 mx-8 text-blue-300/70 text-xs font-medium uppercase tracking-widest whitespace-nowrap">
            <span className="text-blue-400">{item.icon}</span>
            <span>{item.text}</span>
            <span className="text-white/20 ml-8">◆</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function Architecture() {
  const services = [
    { icon: <Car className="w-6 h-6" />, name: 'OBU Simulator', color: '#3b82f6',
      description: 'Simulates vehicle GPS data along NYC routes, publishing to Kafka at configurable intervals.',
      tags: ['GPS', 'Kafka Producer', 'NYC Route'], metric: '1 vehicle/s', metricLabel: 'event rate' },
    { icon: <Cpu className="w-6 h-6" />, name: 'Toll Processor', color: '#06b6d4',
      description: 'Consumes GPS stream, runs PostGIS geofence detection, calculates Haversine tolls, publishes events.',
      tags: ['PostGIS', 'Redis', 'Haversine'], metric: '< 5ms', metricLabel: 'avg latency' },
    { icon: <Server className="w-6 h-6" />, name: 'Billing Service', color: '#8b5cf6',
      description: 'Idempotent payment processing, REST API with Swagger, Prometheus metrics, distributed tracing.',
      tags: ['FastAPI', 'PostgreSQL', 'REST API'], metric: '99.1%', metricLabel: 'success rate' },
  ]
  return (
    <section id="platform" className="section-padding" style={{ background: '#050810' }}>
      <div className="max-w-7xl mx-auto">
        <FadeIn>
          <div className="flex items-center gap-3 mb-4">
            <div className="h-px w-6 bg-white/30" />
            <span className="text-xs font-semibold uppercase tracking-widest text-white/40">Architecture</span>
          </div>
          <h2 className="text-4xl md:text-5xl font-black tracking-tighter mb-4">
            Three Services.<br /><span style={{ color: 'rgba(242,242,242,0.4)' }}>One Seamless Pipeline.</span>
          </h2>
          <p className="text-white/50 max-w-xl mb-6 text-lg">Event-driven microservices architecture built for throughput, resilience, and observability.</p>
        </FadeIn>
        <div className="grid md:grid-cols-3 gap-6 mb-6">
          {services.map((svc, i) => (
            <FadeIn key={svc.name} delay={i * 0.15}>
              <div className="card-glass card-hover rounded-2xl p-6 h-full" style={{ border: '1px solid rgba(255,255,255,0.06)', borderTop: `2px solid ${svc.color}` }}>
                <div className="flex items-start justify-between mb-6">
                  <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{ background: `${svc.color}20`, border: `1px solid ${svc.color}30` }}>
                    <span style={{ color: svc.color }}>{svc.icon}</span>
                  </div>
                  <div className="text-right">
                    <p className="text-xs font-mono text-white/30">{svc.metricLabel}</p>
                    <p className="text-lg font-bold font-mono" style={{ color: svc.color }}>{svc.metric}</p>
                  </div>
                </div>
                <h3 className="font-bold text-lg text-white mb-2">{svc.name}</h3>
                <p className="text-white/50 text-sm mb-4 leading-relaxed">{svc.description}</p>
                <div className="flex flex-wrap gap-2">
                  {svc.tags.map(tag => (
                    <span key={tag} className="px-2 py-0.5 text-xs rounded-md font-mono"
                      style={{ background: `${svc.color}10`, color: svc.color, border: `1px solid ${svc.color}20` }}>{tag}</span>
                  ))}
                </div>
              </div>
            </FadeIn>
          ))}
        </div>
        <FadeIn>
          <div className="rounded-2xl p-6 md:p-8" style={{ background: 'rgba(11,16,27,0.8)', border: '1px solid rgba(59,130,246,0.1)' }}>
            <p className="text-xs font-semibold uppercase tracking-widest text-white/30 mb-6">Shared Infrastructure</p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { icon: <CloudLightning className="w-5 h-5" />, name: 'Apache Kafka', desc: 'Event streaming', color: '#f59e0b' },
                { icon: <Database className="w-5 h-5" />, name: 'PostgreSQL + PostGIS', desc: 'Spatial database', color: '#22c55e' },
                { icon: <Zap className="w-5 h-5" />, name: 'Redis', desc: 'Vehicle state cache', color: '#ef4444' },
                { icon: <BarChart3 className="w-5 h-5" />, name: 'Prometheus', desc: 'Metrics + alerting', color: '#e87d14' },
              ].map((infra) => (
                <div key={infra.name} className="flex items-center gap-3 p-3 rounded-xl" style={{ background: 'rgba(255,255,255,0.03)' }}>
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: `${infra.color}15` }}>
                    <span style={{ color: infra.color }}>{infra.icon}</span>
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-white">{infra.name}</p>
                    <p className="text-xs text-white/40">{infra.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </FadeIn>
      </div>
    </section>
  )
}

const LOG_TEMPLATES = [
  { level: 'INFO', msg: 'GPS event received: vehicle_id=V-4821, lat=40.7142, lon=-74.0063', service: 'obu_simulator' },
  { level: 'INFO', msg: 'Zone entry detected: zone=Zone1, vehicle=V-4821', service: 'toll_processor' },
  { level: 'INFO', msg: 'Toll calculated: $2.50 (haversine=0.82km)', service: 'toll_processor' },
  { level: 'INFO', msg: 'Toll event published to kafka: toll_events', service: 'toll_processor' },
  { level: 'INFO', msg: 'Billing transaction created: txn_id=TXN-8821', service: 'billing_service' },
  { level: 'INFO', msg: 'Payment processed: gateway=MOCK, status=SUCCESS', service: 'billing_service' },
  { level: 'WARN', msg: 'GPS timestamp delta: 4.2s — within threshold', service: 'toll_processor' },
  { level: 'INFO', msg: 'Zone exit detected: zone=Zone1, vehicle=V-4821', service: 'toll_processor' },
  { level: 'INFO', msg: 'Redis state updated: TTL=21600s', service: 'toll_processor' },
  { level: 'INFO', msg: 'Idempotency check passed: toll_event_id=EVT-0044', service: 'billing_service' },
]

function KernelLog() {
  const [logs, setLogs] = useState<Array<{ ts: string; level: string; msg: string; service: string }>>([])
  useEffect(() => {
    const interval = setInterval(() => {
      const tpl = LOG_TEMPLATES[Math.floor(Math.random() * LOG_TEMPLATES.length)]
      const now = new Date()
      const ts = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}:${String(now.getSeconds()).padStart(2,'0')}.${String(now.getMilliseconds()).padStart(3,'0')}`
      setLogs(prev => [...prev.slice(-14), { ts, ...tpl }])
    }, 800)
    return () => clearInterval(interval)
  }, [])
  const levelColor = (level: string) => {
    if (level === 'WARN') return '#f59e0b'
    if (level === 'ERROR') return '#ef4444'
    return '#22c55e'
  }
  const serviceColor = (svc: string) => {
    if (svc === 'toll_processor') return '#06b6d4'
    if (svc === 'billing_service') return '#8b5cf6'
    return '#3b82f6'
  }
  return (
    <section id="services" className="section-padding" style={{ background: '#07090f' }}>
      <div className="max-w-7xl mx-auto">
        <div className="grid lg:grid-cols-2 gap-12 items-center">
          <FadeIn direction="left">
            <div className="flex items-center gap-3 mb-4">
              <div className="h-px w-6 bg-white/30" />
              <span className="text-xs font-semibold uppercase tracking-widest text-white/40">Live System</span>
            </div>
            <h2 className="text-4xl md:text-5xl font-black tracking-tighter mb-6">
              Real-time event<br /><span style={{ color: 'rgba(242,242,242,0.4)' }}>processing engine.</span>
            </h2>
            <p className="text-white/50 text-lg leading-relaxed mb-8">
              Every GPS ping triggers a cascade: geofence detection, toll calculation, Kafka event emission, and payment processing — all within single-digit milliseconds.
            </p>
            <div className="grid grid-cols-2 gap-4">
              {[
                { label: 'GPS Validation', desc: '±10 min timestamp window' },
                { label: 'Spatial Index', desc: 'PostGIS GiST on toll zones' },
                { label: 'State TTL', desc: '6-hour Redis expiry' },
                { label: 'Deduplication', desc: 'Idempotent by event ID' },
              ].map(item => (
                <div key={item.label} className="p-4 rounded-xl" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.05)' }}>
                  <p className="text-sm font-semibold text-white mb-1">{item.label}</p>
                  <p className="text-xs text-white/40 font-mono">{item.desc}</p>
                </div>
              ))}
            </div>
          </FadeIn>
          <FadeIn direction="right">
            <div className="rounded-2xl overflow-hidden" style={{ background: '#0a0d16', border: '1px solid rgba(59,130,246,0.15)' }}>
              <div className="flex items-center justify-between px-4 py-3" style={{ background: '#0f1420', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-red-500/60" />
                  <div className="w-3 h-3 rounded-full bg-yellow-500/60" />
                  <div className="w-3 h-3 rounded-full bg-green-500/60" />
                </div>
                <span className="text-xs text-white/30 font-mono">smarttoll — kernel log</span>
                <div className="flex items-center gap-1.5 text-green-400">
                  <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
                  <span className="text-xs font-mono">LIVE</span>
                </div>
              </div>
              <div className="p-4 h-72 overflow-hidden font-mono text-xs space-y-1">
                {logs.length === 0 && <div className="text-white/20">Connecting to kernel log...</div>}
                {logs.map((log, i) => (
                  <motion.div key={i} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} className="flex gap-2 items-start">
                    <span className="text-white/25 shrink-0">{log.ts}</span>
                    <span className="shrink-0 font-bold" style={{ color: levelColor(log.level) }}>[{log.level}]</span>
                    <span className="shrink-0 font-semibold" style={{ color: serviceColor(log.service) }}>{log.service}:</span>
                    <span className="text-white/60 break-all">{log.msg}</span>
                  </motion.div>
                ))}
              </div>
            </div>
          </FadeIn>
        </div>
      </div>
    </section>
  )
}

function Stats() {
  const statsData = [
    { value: '< 5ms', label: 'GPS Processing Latency', desc: 'Kafka → PostGIS → Redis round trip', icon: <Zap className="w-5 h-5" />, color: '#3b82f6' },
    { value: '99.1%', label: 'Payment Success Rate', desc: 'MOCK gateway, idempotent retries', icon: <CheckCircle2 className="w-5 h-5" />, color: '#22c55e' },
    { value: '6 hr', label: 'Vehicle State TTL', desc: 'Redis key expiry per vehicle', icon: <Clock className="w-5 h-5" />, color: '#06b6d4' },
    { value: '∞', label: 'Event Replay', desc: 'Kafka auto_offset_reset=earliest', icon: <Activity className="w-5 h-5" />, color: '#8b5cf6' },
  ]
  return (
    <section style={{ background: '#050810', borderTop: '1px solid rgba(59,130,246,0.1)', borderBottom: '1px solid rgba(59,130,246,0.1)' }}>
      <div className="max-w-7xl mx-auto grid grid-cols-2 md:grid-cols-4" style={{ borderLeft: '1px solid rgba(255,255,255,0.04)' }}>
        {statsData.map((stat, i) => (
          <FadeIn key={stat.label} delay={i * 0.1}>
            <div className="p-7 md:p-9 flex flex-col gap-2" style={{ borderRight: '1px solid rgba(255,255,255,0.04)' }}>
              <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: `${stat.color}15`, color: stat.color }}>
                {stat.icon}
              </div>
              <p className="text-3xl md:text-4xl font-black tracking-tighter mt-1" style={{ color: stat.color }}>{stat.value}</p>
              <p className="text-sm font-semibold text-white/70">{stat.label}</p>
              <p className="text-xs text-white/30 font-mono leading-relaxed">{stat.desc}</p>
            </div>
          </FadeIn>
        ))}
      </div>
    </section>
  )
}

function ApiSection() {
  const endpoints = [
    { method: 'GET', path: '/api/v1/health/live', auth: false, desc: 'Liveness probe' },
    { method: 'GET', path: '/api/v1/health/ready', auth: false, desc: 'Readiness (DB + Kafka check)' },
    { method: 'GET', path: '/api/v1/transactions', auth: true, desc: 'List transactions (paginated, filterable)' },
    { method: 'GET', path: '/api/v1/transactions/{id}', auth: true, desc: 'Get transaction by internal ID' },
    { method: 'GET', path: '/api/v1/transactions/status/{toll_event_id}', auth: true, desc: 'Get by Toll Event ID' },
    { method: 'GET', path: '/metrics', auth: false, desc: 'Prometheus metrics scrape endpoint' },
  ]
  const methodColor = (m: string) => m === 'POST' ? '#22c55e' : '#3b82f6'
  return (
    <section id="api" className="section-padding" style={{ background: '#050810' }}>
      <div className="max-w-7xl mx-auto">
        <FadeIn>
          <div className="flex items-center gap-3 mb-4">
            <div className="h-px w-6 bg-white/30" />
            <span className="text-xs font-semibold uppercase tracking-widest text-white/40">REST API</span>
          </div>
          <h2 className="text-4xl md:text-5xl font-black tracking-tighter mb-4">
            OpenAPI documented.<br /><span style={{ color: 'rgba(242,242,242,0.4)' }}>Production ready.</span>
          </h2>
          <p className="text-white/50 text-lg max-w-xl mb-8">
            Full Swagger UI at <code className="font-mono text-blue-400 text-sm bg-blue-400/10 px-2 py-0.5 rounded">localhost:8001/docs</code> with request/response schemas and live testing.
          </p>
        </FadeIn>
        <div className="grid lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2">
            <FadeIn>
              <div className="rounded-2xl overflow-hidden" style={{ background: '#0a0d16', border: '1px solid rgba(255,255,255,0.06)' }}>
                <div className="px-6 py-4 flex items-center gap-3" style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', background: '#0f1420' }}>
                  <Code2 className="w-4 h-4 text-blue-400" />
                  <span className="text-sm font-semibold text-white">Billing Service — API Endpoints</span>
                  <span className="ml-auto px-2 py-0.5 text-xs rounded font-mono" style={{ background: 'rgba(59,130,246,0.1)', color: '#60a5fa' }}>:8001</span>
                </div>
                <div className="divide-y" style={{ borderColor: 'rgba(255,255,255,0.04)' }}>
                  {endpoints.map((ep, i) => (
                    <motion.div key={i} className="flex items-center gap-4 px-6 py-4 transition-colors" whileHover={{ x: 4 }}>
                      <span className="text-xs font-bold font-mono w-10 shrink-0" style={{ color: methodColor(ep.method) }}>{ep.method}</span>
                      <code className="text-sm font-mono text-white/80 flex-1">{ep.path}</code>
                      {ep.auth && (
                        <span className="px-2 py-0.5 text-xs rounded font-mono" style={{ background: 'rgba(139,92,246,0.1)', color: '#a78bfa', border: '1px solid rgba(139,92,246,0.2)' }}>X-API-KEY</span>
                      )}
                      <span className="text-xs text-white/30 hidden md:block">{ep.desc}</span>
                    </motion.div>
                  ))}
                </div>
              </div>
            </FadeIn>
          </div>
          <FadeIn delay={0.2} direction="right">
            <div className="space-y-4">
              <div className="card-glass card-hover rounded-2xl p-6">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-4" style={{ background: 'rgba(59,130,246,0.1)' }}>
                  <Shield className="w-5 h-5 text-blue-400" />
                </div>
                <h3 className="font-bold text-white mb-2">API Key Auth</h3>
                <p className="text-sm text-white/50">Constant-time HMAC key comparison. Set via <code className="font-mono text-xs text-blue-400">SERVICE_API_KEY</code> env var.</p>
              </div>
              <div className="card-glass card-hover rounded-2xl p-6">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-4" style={{ background: 'rgba(6,182,212,0.1)' }}>
                  <GitBranch className="w-5 h-5 text-cyan-400" />
                </div>
                <h3 className="font-bold text-white mb-2">Request Tracing</h3>
                <p className="text-sm text-white/50">Every response includes <code className="font-mono text-xs text-cyan-400">X-Request-ID</code> header for distributed tracing.</p>
              </div>
              <div className="card-glass card-hover rounded-2xl p-6">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-4" style={{ background: 'rgba(139,92,246,0.1)' }}>
                  <BarChart3 className="w-5 h-5 text-purple-400" />
                </div>
                <h3 className="font-bold text-white mb-2">Prometheus Metrics</h3>
                <p className="text-sm text-white/50">Transaction counters, payment duration histograms, Kafka consumer throughput.</p>
              </div>
            </div>
          </FadeIn>
        </div>
      </div>
    </section>
  )
}

function About() {
  const features = [
    { icon: <Map className="w-6 h-6" />, color: '#3b82f6', title: 'Geospatial Intelligence',
      desc: 'PostGIS ST_Contains with GiST spatial indexes for sub-millisecond zone entry/exit detection across thousands of zones.' },
    { icon: <AlertCircle className="w-6 h-6" />, color: '#ef4444', title: 'Fault Tolerance',
      desc: 'Kafka consumer with auto_offset_reset=earliest ensures zero event loss on restart.' },
    { icon: <Layers className="w-6 h-6" />, color: '#22c55e', title: 'Idempotency',
      desc: 'Deduplication by toll_event_id prevents duplicate billing transactions.' },
    { icon: <Globe className="w-6 h-6" />, color: '#f59e0b', title: 'Deploy Anywhere',
      desc: 'Docker Compose for local dev. Kubernetes/ECS/Fly.io ready with health probes and Prometheus scrape endpoints baked in.' },
  ]
  return (
    <section id="about" className="section-padding" style={{ background: '#07090f' }}>
      <div className="max-w-7xl mx-auto">
        <FadeIn>
          <div className="flex items-center gap-3 mb-4">
            <div className="h-px w-6 bg-white/30" />
            <span className="text-xs font-semibold uppercase tracking-widest text-white/40">About</span>
          </div>
          <h2 className="text-4xl md:text-5xl font-black tracking-tighter mb-4">
            Built for reliability.<br /><span style={{ color: 'rgba(242,242,242,0.4)' }}>Engineered for scale.</span>
          </h2>
          <p className="text-white/50 text-lg max-w-xl mb-8">SmartToll is a production-grade microservices platform using battle-tested infrastructure at every layer.</p>
        </FadeIn>
        <div className="grid md:grid-cols-2 gap-4">
          {features.map((feat, i) => (
            <FadeIn key={feat.title} delay={i * 0.1}>
              <div className="card-glass card-hover rounded-2xl p-8 h-full" style={{ border: '1px solid rgba(255,255,255,0.06)', borderTop: `2px solid ${feat.color}` }}>
                <div className="w-12 h-12 rounded-xl flex items-center justify-center mb-5" style={{ background: `${feat.color}15`, border: `1px solid ${feat.color}25` }}>
                  <span style={{ color: feat.color }}>{feat.icon}</span>
                </div>
                <h3 className="text-lg font-bold text-white mb-3">{feat.title}</h3>
                <p className="text-white/50 text-sm leading-relaxed">{feat.desc}</p>
              </div>
            </FadeIn>
          ))}
        </div>
      </div>
    </section>
  )
}

function CTA() {
  return (
    <section className="section-padding" style={{ background: '#050810' }}>
      <div className="max-w-7xl mx-auto">
        <FadeIn>
          <div className="relative overflow-hidden rounded-3xl p-10 md:p-16 text-center"
            style={{ background: 'linear-gradient(135deg, rgba(59,130,246,0.12), rgba(6,182,212,0.08))', border: '1px solid rgba(59,130,246,0.2)' }}>
            <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 w-64 h-64 rounded-full pointer-events-none"
              style={{ background: 'radial-gradient(circle, rgba(59,130,246,0.2) 0%, transparent 70%)' }} />
            <div className="relative z-10 flex flex-col items-center">
              <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs font-semibold uppercase tracking-widest mb-8"
                style={{ border: '1px solid rgba(59,130,246,0.3)', background: 'rgba(59,130,246,0.1)', color: '#60a5fa' }}>
                <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
                Start Today
              </div>
              <h2 className="text-4xl md:text-6xl font-black tracking-tighter text-white mb-6 text-center">
                Deploy the future<br />
                <span style={{ background: 'linear-gradient(135deg, #3b82f6, #06b6d4)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                  of toll infrastructure.
                </span>
              </h2>
              <p className="text-white/50 text-lg max-w-xl mb-8 text-center">
                One command. Full Kafka, PostgreSQL, Redis, and three microservices — ready in under 2 minutes.
              </p>
              {/* Quick start code block */}
              <div className="w-full max-w-lg mb-10 rounded-xl overflow-hidden text-left" style={{ background: '#0a0d16', border: '1px solid rgba(59,130,246,0.2)' }}>
                <div className="flex items-center gap-2 px-4 py-2.5" style={{ background: '#0f1420', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                  <Terminal className="w-3.5 h-3.5 text-blue-400" />
                  <span className="text-xs text-white/40 font-mono">Quick Start</span>
                </div>
                <div className="px-4 py-4 space-y-1.5 font-mono text-sm">
                  <p><span className="text-white/30"># 1. Copy env file</span></p>
                  <p><span className="text-blue-400">cp</span> <span className="text-white/70">.env.example .env</span></p>
                  <p className="pt-1"><span className="text-white/30"># 2. Start all 7 services</span></p>
                  <p><span className="text-blue-400">docker</span> <span className="text-cyan-400">compose</span> <span className="text-white/70">up -d</span></p>
                  <p className="pt-1"><span className="text-white/30"># 3. Open Swagger UI</span></p>
                  <p><span className="text-blue-400">open</span> <span className="text-green-400">http://localhost:8001/docs</span></p>
                </div>
              </div>
              <div className="flex flex-wrap gap-4 justify-center">
                <a href="http://localhost:8001/docs" target="_blank" rel="noopener noreferrer" className="btn-primary flex items-center gap-2 px-8 py-4">
                  Open Swagger UI
                  <div className="w-6 h-6 rounded-full flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.3)' }}>
                    <ArrowUpRight className="w-3.5 h-3.5" />
                  </div>
                </a>
                <a href="https://github.com/hooiv/smarttoll-prod" target="_blank" rel="noopener noreferrer"
                  className="flex items-center gap-2 px-8 py-4 rounded-full text-white/70 hover:text-white transition-all duration-300"
                  style={{ border: '1px solid rgba(255,255,255,0.1)' }}>
                  View on GitHub <ExternalLink className="w-4 h-4" />
                </a>
              </div>
            </div>
          </div>
        </FadeIn>
      </div>
    </section>
  )
}

function Footer() {
  const year = new Date().getFullYear()
  return (
    <footer style={{ background: '#030508', borderTop: '1px solid rgba(59,130,246,0.08)' }}>
      <div className="max-w-7xl mx-auto px-7 py-16 md:px-12 lg:px-20">
        <div className="grid md:grid-cols-4 gap-10 mb-12">
          <div className="md:col-span-2">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #3b82f6, #06b6d4)' }}>
                <Navigation className="w-4 h-4 text-white" />
              </div>
              <span className="font-bold text-lg tracking-tight text-white">Smart<span style={{ color: '#3b82f6' }}>Toll</span></span>
            </div>
            <p className="text-white/40 text-sm max-w-xs leading-relaxed">Intelligent, event-driven toll processing system built on Apache Kafka, PostGIS, and Redis.</p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-white/30 mb-4">Services</p>
            <ul className="space-y-2">
              {['OBU Simulator', 'Toll Processor', 'Billing Service', 'Prometheus Metrics'].map(l => (
                <li key={l}><a href="#" className="text-sm text-white/40 hover:text-white transition-colors">{l}</a></li>
              ))}
            </ul>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-white/30 mb-4">API</p>
            <ul className="space-y-2">
              {[
                { label: 'Swagger UI', href: 'http://localhost:8001/docs' },
                { label: 'ReDoc', href: 'http://localhost:8001/redoc' },
                { label: 'Health Check', href: 'http://localhost:8001/api/v1/health/live' },
                { label: 'Metrics', href: 'http://localhost:8001/metrics' },
              ].map(l => (
                <li key={l.label}>
                  <a href={l.href} target="_blank" rel="noopener noreferrer" className="text-sm text-white/40 hover:text-white transition-colors flex items-center gap-1">
                    {l.label} <ExternalLink className="w-3 h-3" />
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </div>
        <div className="flex flex-col md:flex-row items-center justify-between pt-8 gap-4" style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}>
          <p className="text-xs text-white/25 font-mono">© {year} SmartToll. All rights reserved.</p>
          <div className="flex items-center gap-2 text-xs font-mono">
            <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
            <span className="text-green-400/60">System Operational</span>
          </div>
        </div>
        <div className="mt-8 overflow-hidden select-none pointer-events-none">
          <p className="font-black text-white leading-none tracking-tighter" style={{ fontSize: 'clamp(3rem, 12vw, 10rem)', opacity: 0.03 }}>SMARTTOLL</p>
        </div>
      </div>
    </footer>
  )
}

export default function App() {
  return (
    <>
      <div className="noise-overlay" />
      <Navbar />
      <main>
        <Hero />
        <MarqueeBar />
        <Architecture />
        <KernelLog />
        <Stats />
        <ApiSection />
        <About />
        <CTA />
      </main>
      <Footer />
    </>
  )
}
