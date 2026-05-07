#pragma once
#include "BaseScene.h"
#include <vector>
#include <memory>
#include "Object3d.h"
#include "LevelLoader.h"

/// <summary>
/// レベルローダーの使用例を示すサンプルシーンクラス
/// </summary>
class SampleGameScene : public BaseScene {
public:
	void Initialize() override;
	void Update() override;
	void Draw() override;
	void Finalize() override;

private:
	/// <summary>
	/// レベルデータからオブジェクトを再帰的に生成する
	/// </summary>
	/// <param name="data">オブジェクトデータの配列</param>
	void CreateObjects(const std::vector<LevelData::ObjectData>& data);

private:
	// 読み込まれたレベルデータ
	std::unique_ptr<LevelData> levelData_;
	// 生成された3Dオブジェクトのリスト
	std::vector<std::unique_ptr<Object3d>> objects_;
};
