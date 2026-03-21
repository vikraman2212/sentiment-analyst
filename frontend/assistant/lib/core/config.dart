import 'package:shared_preferences/shared_preferences.dart';

const _kBaseUrlKey = 'api_base_url';
const _kDefaultBaseUrl = 'http://localhost:8000';

Future<String> getBaseUrl() async {
  final prefs = await SharedPreferences.getInstance();
  return prefs.getString(_kBaseUrlKey) ?? _kDefaultBaseUrl;
}

Future<void> setBaseUrl(String url) async {
  final prefs = await SharedPreferences.getInstance();
  await prefs.setString(_kBaseUrlKey, url);
}
