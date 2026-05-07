#pragma once

#include <string>
#include <vector>
#include "MathTypes.h"

// json.hpp をインクルードする代わりに前方宣言を試みるのは複雑なため、
// 実際の利用時には json.hpp が必要です。
#include <json.hpp>

// レベルデータ
struct LevelData {

	struct ObjectData {
		// 種類 (MESH, LIGHT, CAMERA, EMPTY etc...)
		std::string type;
		// オブジェクト名
		std::string name;
		// モデルファイル名 (MESHのみ)
		std::string fileName;
		// 平行移動
		Vector3 translation;
		// 回転角 (ラジアン)
		Vector3 rotation;
		// スケーリング
		Vector3 scaling;
		// 子要素
		std::vector<ObjectData> children;
	};

	// ルートオブジェクトの配列
	std::vector<ObjectData> objects;
};

/// <summary>
/// Blenderから出力されたJSONレベルデータを読み込むクラス
/// </summary>
class LevelLoader {

public:// 定数
	// デフォルトの読み込みディレクトリ
	static const std::string kDefaultBaseDirectory;
	// ファイル拡張子
	static const std::string kExtension;

public:// メンバ関数
	
	/// <summary>
	/// レベルデータファイルの読み込み
	/// </summary>
	/// <param name="fileName">ファイル名 (拡張子なし)</param>
	/// <returns>読み込まれたレベルデータ。不要になったらdeleteすること。</returns>
	static LevelData* LoadFile(const std::string& fileName);

private:
	/// <summary>
	/// オブジェクトとその子要素を再帰的にパースする
	/// </summary>
	/// <param name="objectData">格納先の参照</param>
	/// <param name="jsonObject">パース対象のJSONオブジェクト</param>
	static void ParseObject(LevelData::ObjectData& objectData, const nlohmann::json& jsonObject);
};
