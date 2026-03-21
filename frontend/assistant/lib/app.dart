import 'package:flutter/material.dart';
import 'features/capture/capture_screen.dart';
import 'features/inbox/inbox_screen.dart';
import 'settings/settings_screen.dart';

class App extends StatefulWidget {
  const App({super.key});

  @override
  State<App> createState() => _AppState();
}

class _AppState extends State<App> {
  int _currentIndex = 0;

  static const _screens = [
    CaptureScreen(),
    InboxScreen(),
  ];

  static const _tabs = [
    BottomNavigationBarItem(
      icon: Icon(Icons.mic),
      label: 'Capture',
    ),
    BottomNavigationBarItem(
      icon: Icon(Icons.inbox),
      label: 'Inbox',
    ),
  ];

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Sentiment Analyst',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF1A73E8)),
        useMaterial3: true,
      ),
      home: Scaffold(
        appBar: AppBar(
          title: const Text('Sentiment Analyst'),
          actions: [
            IconButton(
              icon: const Icon(Icons.settings),
              tooltip: 'Settings',
              onPressed: () => Navigator.push(
                context,
                MaterialPageRoute(
                    builder: (_) => const SettingsScreen()),
              ),
            ),
          ],
        ),
        body: _screens[_currentIndex],
        bottomNavigationBar: BottomNavigationBar(
          currentIndex: _currentIndex,
          onTap: (i) => setState(() => _currentIndex = i),
          items: _tabs,
        ),
      ),
    );
  }
}
